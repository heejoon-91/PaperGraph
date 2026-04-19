# Gemma 4 E4B Local Hugging Face Setup

## Current Machine

- GPU: NVIDIA GeForce RTX 4060
- VRAM: 8 GB
- Driver-reported CUDA: 12.2
- Installed PyTorch runtime: `torch 2.5.1+cu121`
- Disk free before model download: about 122 GB on `C:`

## Local Paths

- Training env: `C:\workspace\papergraph\.conda-train`
- HF cache: `C:\workspace\papergraph\.cache\huggingface`
- Downloaded model: `C:\workspace\papergraph\models\gemma-4-E4B-it`
- Main weight file: `models\gemma-4-E4B-it\model.safetensors`
- Downloaded model size: about 14.9 GiB on disk

The Ollama path under `C:\Users\OWNER\.ollama\models\manifests\registry.ollama.ai\library\gemma4` is only the Ollama manifest. The actual Ollama blob is quantized for Ollama inference, so this Hugging Face safetensors copy is the one to use for PEFT/TRL training work.

## Environment

The working Python environment is a local conda prefix, not the earlier Python 3.13 venv attempt:

```powershell
.\.conda-train\python.exe --version
```

Installed core packages:

- `torch 2.5.1+cu121`
- `transformers 5.5.4`
- `peft 0.19.1`
- `trl 1.2.0`
- `accelerate 1.13.0`
- `bitsandbytes 0.49.2`
- `datasets`, `safetensors`, `huggingface_hub`

Use this command shape for all training scripts:

```powershell
$env:PYTHONNOUSERSITE='1'
.\.conda-train\python.exe <script.py>
```

## Download Command

The model was downloaded with the new HF CLI:

```powershell
$env:PYTHONNOUSERSITE='1'
$env:HF_HOME='C:\workspace\papergraph\.cache\huggingface'
.\.conda-train\Scripts\hf.exe download google/gemma-4-E4B-it --local-dir models\gemma-4-E4B-it
```

The download succeeded unauthenticated in this run, but HF warned that an `HF_TOKEN` gives higher rate limits and faster downloads.

## Smoke Test

Config and processor load succeeded locally:

- model type: `gemma4`
- text layers: `42`
- hidden size: `2560`
- context length: `131072`
- processor: `Gemma4Processor`

The full multimodal model with automatic 4-bit device mapping did not fit cleanly on the 8 GB GPU. The text-only causal LM path did load in 4-bit and generated a valid response.

Run the reproducible smoke test:

```powershell
$env:PYTHONNOUSERSITE='1'
.\.conda-train\python.exe scripts\smoke_gemma4_hf.py
```

Observed output:

````text
```json
{
  "status": "ok"
}
```
max_memory_gb=8.942
````

The reported peak is tight for an 8 GB card because CUDA allocation accounting includes reserved/managed memory behavior. For actual fine-tuning, keep sequence length and batch size small and use gradient accumulation.

## Practical Training Direction

For this machine, use LoRA/QLoRA against the text-only model path first:

- `load_in_4bit=True`
- target text model modules only
- small sequence length first, such as 1024 or 2048
- per-device train batch size `1`
- gradient accumulation to reach the effective batch size
- save adapters only, not a full merged model

The full multimodal `Gemma4ForConditionalGeneration` path is useful for later multimodal inference tests, but it is not the right first target for local 8 GB VRAM fine-tuning.

## Training Run

SFT data was generated from the effective v1 labels:

```text
effective labels: accept 740, edit 47, reject 213
extractor train/eval: 559 / 40
judge train/eval: 932 / 68
```

The generated SFT files are derived artifacts under `train/` and are ignored by git. Rebuild them with:

```powershell
python scripts\build_gemma4_sft_data.py
```

The first stable local training run used the extractor data only:

```powershell
$env:PYTHONNOUSERSITE='1'
$env:PYTHONUTF8='1'
.\.conda-train\python.exe scripts\train_gemma4_lora.py `
  --output-dir outputs\gemma4-e4b-papergraph-extractor-lora `
  --max-steps 20 `
  --max-length 256 `
  --gradient-accumulation-steps 2 `
  --learning-rate 5e-5
```

Training completed and saved the adapter:

```text
trainable params: 2,269,184
all params: 7,943,370,016
trainable: 0.0286%
train_loss: 5.996
runtime: 1159 seconds
adapter: outputs\gemma4-e4b-papergraph-extractor-lora
```

The 8 GB GPU is the bottleneck. At `max_length=256`, one optimizer step takes about one minute. A rough single epoch over the current extractor train split is about 70 steps with the current effective batch settings.

Evaluation command:

```powershell
$env:PYTHONNOUSERSITE='1'
$env:PYTHONUTF8='1'
.\.conda-train\python.exe scripts\eval_gemma4_lora.py `
  --adapter-dir outputs\gemma4-e4b-papergraph-extractor-lora `
  --limit 4 `
  --max-new-tokens 192
```

Initial evaluation result:

```text
total: 4
json_valid: 1
schema_ok: 0
```

This means the local training pipeline works end to end, but 20 steps is not enough to make the extractor reliably follow the PaperGraph schema. The next useful run is a longer extractor run, then a separate judge adapter run.
