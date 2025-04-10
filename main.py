import logging
import os
import signal
import sys
import time
import uuid
from concurrent.futures import wait, Executor
from concurrent.futures.thread import ThreadPoolExecutor
from logging import config
from queue import Queue
from threading import Lock
from typing import List

import httpx
import pandas
import yaml
from dotenv import load_dotenv
from openai import OpenAI

from verifiers import TextVerifier

LOGGING_CONF = "logging.conf"
with open(LOGGING_CONF, "r") as f:
    d = yaml.safe_load(f)
logging.config.dictConfig(d)

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
logger = logging.getLogger()
verifier_logger = logging.getLogger('verifier')

load_dotenv()

# Config
_threads = int(os.environ.get("THREADS", 10))
logger.info(f"THREADS={_threads}")
_iterations = int(os.environ.get("ITERATIONS", 100))
logger.info(f"ITERATIONS={_iterations}")
_endpoint = os.environ.get("ENDPOINT", None)
logger.info(f"ENDPOINT={_endpoint}")
_verifier_endpoint = os.environ.get("VERIFIER_ENDPOINT", None)
logger.info(f"VERIFIER_ENDPOINT={_verifier_endpoint}")
_input = os.environ.get("INPUT", 'dailymail_5k50_70k50.csv')
logger.info(f"INPUT={_input}")
_model = os.environ.get("MODEL", None)
logger.info(f"MODEL={_model}")
_verifier_model = os.environ.get("VERIFIER_MODEL", None)
logger.info(f"VERIFIER_MODEL={_verifier_model}")

# Global Objects
_system_prompt = "Summarize below text."
_lock: Lock = Lock()
_client: OpenAI = None


def get_client(singleton: bool = True):
    global _client
    l_x_api_key = os.environ.get("X_API_KEY", "")
    l_hc = httpx.Client(verify=False)
    l_headers = {"X-API-Key": l_x_api_key}
    try:
        if singleton:
            _lock.acquire()
            if _client is not None:
                logger.debug("Client singleton returned...")
                return _client
        logger.info("Client created...")
        cl = OpenAI(default_headers=l_headers,
                    base_url=_endpoint,
                    api_key="not used",
                    http_client=l_hc)
        if singleton and _client is None:
            _client = cl
        return cl
    finally:
        if singleton:
            _lock.release()


def load_data(fn: str) -> List[str]:
    c = pandas.read_csv(fn)
    l = c['text'].tolist()
    return l


def load_thread(i: int, client: OpenAI, prompt_queue: Queue, model: str, verifier: TextVerifier):
    '''
    Load thread is generating sometimes heavy sometimes light summarization task on the model.
    :return:
    '''
    try:
        prompt = prompt_queue.get()
        uid = uuid.uuid4().hex
        l = len(prompt.split())
        # logger.info(f"{uid} STARTED {l:>7} ")
        bt = time.time()
        completions = client.chat.completions.create(
            messages=[
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": prompt}],
            model=model,
            stream=False
        )
        m = completions.choices[0].message.content
        try:
            v, r = verifier.is_grammatically_correct(m)
            if not v:
                logger.error(f"Suspicious answer - {uid} - {r} \n{m[-300:]}")
                verifier_logger.error(f"{uid} - {r} - {m}")
        except Exception as ve:
            logger.error(ve)
        return completions
    except Exception as me:
        logger.error(me)
    finally:
        et = time.time()
        logger.info(f"{uid} DONE - job {i:>4} - {l:>7} words(s) - {(et - bt):>10} sec(s)")
        logger.debug(f"{uid} response: {completions}")
        prompt_queue.put(prompt)


executor: Executor = None


def killme(signum, frame):
    global executor
    logger.warning("KILLING     >>>")
    executor.shutdown(wait=False, cancel_futures=True)
    logger.warning("FOR IMMEDIATE KILL PRESS CTRL-C AGAIN >>>")
    sys.exit(0)


def run():
    prompts = load_data(_input)
    _prompt_queue = Queue(len(prompts))
    for p in prompts:
        _prompt_queue.put(p)
    _client = get_client()
    x_api_key = os.environ.get("X_API_KEY", "")
    _verifier = TextVerifier(endpoint=_verifier_endpoint, x_api_key=x_api_key, model_name=_verifier_model)
    executor = ThreadPoolExecutor(max_workers=_threads)
    signal.signal(signal.SIGINT, killme)
    futures = []
    for a in range(_threads * _iterations):
        f = executor.submit(load_thread, a, _client, _prompt_queue, _model, _verifier)
        futures.append(f)
    logger.info(f"All {_threads * _iterations} job(s) are submitted...")
    wait(futures)
    logger.info("All {_threads * _iterations} job(s) are done...")


if __name__ == "__main__":
    run()
