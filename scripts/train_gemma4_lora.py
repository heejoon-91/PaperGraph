from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)


os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a Gemma 4 PaperGraph LoRA adapter.")
    parser.add_argument("--model-dir", default="models/gemma-4-E4B-it")
    parser.add_argument("--train-file", default="train/extractor_sft_train.jsonl")
    parser.add_argument("--eval-file", default="train/extractor_sft_eval.jsonl")
    parser.add_argument("--output-dir", default="outputs/gemma4-e4b-papergraph-extractor-lora")
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument(
        "--target-projections",
        default="q_proj,v_proj",
        help="Comma-separated language_model projection suffixes to adapt.",
    )
    return parser.parse_args()


def read_jsonl(path: Path, max_examples: int = 0) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
            if max_examples and len(records) >= max_examples:
                break
    return records


class ChatDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, records: list[dict[str, Any]], tokenizer: Any, max_length: int) -> None:
        self.rows = [self._encode(record, tokenizer, max_length) for record in records]

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        return self.rows[index]

    @staticmethod
    def _encode(record: dict[str, Any], tokenizer: Any, max_length: int) -> dict[str, torch.Tensor]:
        messages = record["messages"]
        prompt_messages = messages[:-1]
        assistant_text = messages[-1]["content"]
        prompt = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        eos = tokenizer.eos_token or ""
        full_text = prompt + assistant_text + eos
        full = tokenizer(full_text, add_special_tokens=False, max_length=max_length, truncation=True)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        labels = list(full["input_ids"])
        prompt_len = min(len(prompt_ids), len(labels))
        labels[:prompt_len] = [-100] * prompt_len
        if all(label == -100 for label in labels):
            labels[-1] = full["input_ids"][-1]
        return {
            "input_ids": torch.tensor(full["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(full["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


@dataclass
class CausalCollator:
    tokenizer: Any

    def __call__(self, features: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        max_len = max(feature["input_ids"].shape[0] for feature in features)
        pad_id = self.tokenizer.pad_token_id
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for feature in features:
            pad = max_len - feature["input_ids"].shape[0]
            batch["input_ids"].append(
                torch.nn.functional.pad(feature["input_ids"], (0, pad), value=pad_id)
            )
            batch["attention_mask"].append(
                torch.nn.functional.pad(feature["attention_mask"], (0, pad), value=0)
            )
            batch["labels"].append(torch.nn.functional.pad(feature["labels"], (0, pad), value=-100))
        return {key: torch.stack(value) for key, value in batch.items()}


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for this training script.")

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        local_files_only=True,
        device_map={"": 0},
        quantization_config=quantization,
        dtype=compute_dtype,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    target_suffixes = tuple(item.strip() for item in args.target_projections.split(",") if item.strip())
    target_modules = [
        name
        for name, _module in model.named_modules()
        if name.startswith("model.language_model.") and name.endswith(target_suffixes)
    ]
    if not target_modules:
        raise SystemExit(f"No language model LoRA targets found for suffixes: {target_suffixes}")

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    train_records = read_jsonl(Path(args.train_file), args.max_examples)
    eval_records = read_jsonl(Path(args.eval_file), min(args.max_examples, 32) if args.max_examples else 64)
    train_dataset = ChatDataset(train_records, tokenizer, args.max_length)
    eval_dataset = ChatDataset(eval_records, tokenizer, args.max_length) if eval_records else None

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        bf16=compute_dtype is torch.bfloat16,
        fp16=compute_dtype is torch.float16,
        gradient_checkpointing=True,
        logging_steps=1,
        save_steps=max(args.max_steps, 1),
        save_total_limit=1,
        eval_strategy="no",
        report_to="none",
        remove_unused_columns=False,
        dataloader_pin_memory=False,
        optim="adamw_torch",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=CausalCollator(tokenizer),
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"saved_adapter={args.output_dir}")


if __name__ == "__main__":
    main()
