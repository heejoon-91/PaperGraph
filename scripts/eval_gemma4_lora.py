from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a PaperGraph Gemma LoRA adapter on JSON validity.")
    parser.add_argument("--model-dir", default="models/gemma-4-E4B-it")
    parser.add_argument("--adapter-dir", default="outputs/gemma4-e4b-papergraph-extractor-lora")
    parser.add_argument("--eval-file", default="train/extractor_sft_eval.jsonl")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    return parser.parse_args()


def read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= limit:
                break
    return records


def json_payload(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def schema_ok(payload: dict[str, Any] | None) -> bool:
    keys = {"claims", "methods", "experiments", "limitations", "concepts", "relations"}
    return isinstance(payload, dict) and keys.issubset(payload.keys()) and all(isinstance(payload[k], list) for k in keys)


def main() -> None:
    args = parse_args()
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.adapter_dir, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        local_files_only=True,
        device_map={"": 0},
        quantization_config=quantization,
        dtype=compute_dtype,
    )
    model = PeftModel.from_pretrained(base, args.adapter_dir, local_files_only=True)
    model.eval()

    results = []
    for record in read_jsonl(Path(args.eval_file), args.limit):
        prompt = tokenizer.apply_chat_template(
            record["messages"][:-1],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        text = tokenizer.decode(output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        payload = json_payload(text)
        results.append(
            {
                "chunk_id": record.get("chunk_id"),
                "json_valid": payload is not None,
                "schema_ok": schema_ok(payload),
                "preview": text[:300],
            }
        )

    summary = {
        "total": len(results),
        "json_valid": sum(1 for row in results if row["json_valid"]),
        "schema_ok": sum(1 for row in results if row["schema_ok"]),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
