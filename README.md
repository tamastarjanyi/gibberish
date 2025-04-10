# What is the issue

Sometimes but frequently TGI server is generating gibberish in the response.
Gibberish can be either just not relevant text (hard to detect) or event completely random strings even in different
spoken (not computer) languages.
This seems to be happening when big contexts are sent parallel and the total context size of the running queries are
close to or exceeding the maximum possible size.
In this case some response contains gibberish. This can "heal itself" if no traffic is sent for a while.
But when traffic start coming again the bug can be hit again within minutes.

# Environment

TGI: 3.0.1, 3.1.1, 3.2.1 Docker images (Tested these but expecting to have it in all.)
Runtime: OpenShift 3.14
GPU: NVIDIA H100 80GB HBM3 (8 GPUS per server but a single GPU is used only)

# What the code does

It has a list of prompts. 50 prompts is less than 5k tokens and 50 prompts is around but less than 70k tokens.
This code is sending those to `ENDPOINT` and asking a summarization.

# Prerequisites

## LLM services

You need 2 instances of for example `meta-llama/Llama-3.1-8B-Instruct`

* One is used to do the summarization of texts and this must be TGI.

>
`text-generation-launcher --model-id meta-llama/Llama-3.1-8B-Instruct --cuda-memory-fraction 0.95 --max-input-tokens 80000 --max-total-tokens 80100 --hostname 127.0.0.1 --port 8080`

* The other - verifier - is used only to verify the response of the first LLM.

> The verifier instance is better to be a vLLM instance because if you are using TGI there is a chance to generate
> gibberish even as a verifier response. But this has a very small chance so you can also go with TGI.

## Conda environment

Create the conda environment.

```bash
conda env create -f environment.yaml
```

# How to run

Create your own `.env` based on the `.env.sample` 

* `THREADS` is the number of threads. On a H100 80GB GPU minimum value should be >=10 to hit the bug. Default is 10.
* `ITERATIONS` is the number of iterations. Number of queries will be `THREADS`*`ITERATIONS`. Default is 100.
* `ENDPOINT` must be set to the URL of your first instance as `https://your.domain.com/v1` (**Yes /v1 must be there.**)
* `VERIFIER_ENDPOINT` must be set to the URL of the verifier instance the same way as `ENDPOINT`
* `INPUT` is the file name. Default is `dailymail_5k50_70k50.csv`
* `X_API_KEY` just in case you need that.

```bash
conda activate gibberish
python main.py
```

# Result

Suspicious answers are logged on the console and in `logs/logging.log` in the below form where the last 300 characters
of the
answer is logged.
`2025-04-09 23:33:41,830 -    ERROR -     load_thread:110  -  59581 / MainProcess - Suspicious answer -  - 56bbd1a82dd249d39f11b80f4b97e179 ...`

If `Suspicous answer` is not evidently wrong full response is also logged in `logs/verifier.log` for verification.
The id `56bbd1a82dd249d39f11b80f4b97e179` can be used to find the full response.

> Note: Unfortunatelly sometimes also false positive responses logged, this is why human verification of the suspicious
> ones are needed.

Some examples:

| Log file      | UUID                             | Example Text                                                                                                                                                      |
|---------------|----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| logging.log.1 | f86a13e4555c4f56b67f33a908ad82ec | noises produced individuals Israel dial MA dial MA evaluation begins shiny ultr breakthrough consider natura among Equina Social leader quietly mile guitar sin]; |
| logging.log.2 | 71c9b9e4d0c4472eac4900d55a1dd84d | ООО тяжело расставить/examples/con_PON.... UPROubesอบmy friendship il won / reint ولكن больше                                                                     |
| logging.log.3 | 172b6dde640f4993983c6aee543f9e17 | .4. Haida cost enemy / synop hac sind indem policies debate mangvery hills head                                                                                   |
| logging.log.4 | f82eb6f352aa4640b5eeba81fbffda2e | examining flaws matches hate rel repetition pains cases considerance +" of souls)?                                                                                |

# Compression to deliver

```bash
tar --exclude=".idea" --exclude="__pycache__" --exclude=".env" -cjv -C .. -f ../gibberish.tar.bz gibberish
```