# RunPod SERVERLESS teacher worker — built from GitHub by RunPod. Base = the OFFICIAL vLLM image: torch + vllm +
# transformers + tokenizers + hf_transfer are pre-installed and MUTUALLY TESTED (this is what kills the 5 pod-setup
# failures — no self-built env, so no PEP668 / torch-ABI / tokenizer-skew / hf_transfer-missing). We add only the
# RunPod SDK + the engine deps + our code, and run the serverless handler instead of the vLLM API server.
FROM vllm/vllm-openai:latest

RUN pip install --no-cache-dir runpod treys numpy

WORKDIR /app
COPY . /app
ENV PYTHONPATH=/app \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    PYTHONUNBUFFERED=1

# the base image's ENTRYPOINT is the vLLM OpenAI server — override it to run OUR serverless handler loop
ENTRYPOINT []
CMD ["python3", "-u", "infra/serverless_handler.py"]
