"""Smoke-test a local Hugging Face Gemma 4 E4B checkout.

This script intentionally loads the text-only causal LM head. The full
multimodal conditional-generation model does not fit comfortably on an 8 GB
RTX 4060 with automatic 4-bit device mapping on Windows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir",
        default="models/gemma-4-E4B-it",
        help="Local Hugging Face model directory.",
    )
    parser.add_argument(
        "--prompt",
        default="Return exactly one JSON object with status set to ok.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=32)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        raise SystemExit(f"Missing model directory: {model_dir}")
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available in this environment.")

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        device_map={"": 0},
        quantization_config=quantization,
        dtype=compute_dtype,
    )

    messages = [{"role": "user", "content": args.prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    output = model.generate(
        **inputs,
        max_new_tokens=args.max_new_tokens,
        do_sample=False,
    )
    generated = output[0][inputs["input_ids"].shape[-1] :]
    print(tokenizer.decode(generated, skip_special_tokens=True).strip())
    print(f"max_memory_gb={torch.cuda.max_memory_allocated() / 1024**3:.3f}")


if __name__ == "__main__":
    main()
