#!/usr/bin/env python3
"""
Gemini Live voice assistant grounded on local KB.

Usage:
  export GEMINI_API_KEY=your-key
  python3 scripts/local_kb_voice.py --mode none

Speak into the mic or type at the message > prompt.
"""

import argparse
import asyncio
import base64
import io
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyaudio
from google import genai
from google.genai import types

from config.settings import LIVE_MODEL
from services import kb_service
from services.voice_service import build_live_connect_config

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
DEFAULT_MODE = "none"

MODEL = LIVE_MODEL

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=os.environ.get("GEMINI_API_KEY"),
)

CONFIG = build_live_connect_config(MODEL)

pya = pyaudio.PyAudio()


def _format_kb_results(results):
    if not results:
        return "No matching articles found."
    parts = []
    for r in results:
        block = f"Title: {r.get('title')}\n{r.get('content', '')[:600]}"
        img = r.get("image")
        if img:
            block += f"\nImage: {img.get('caption', '')} ({img.get('path', '')})"
        parts.append(block)
    return "\n\n---\n\n".join(parts)


async def _handle_tool_call(session, tool_call):
    for fc in tool_call.function_calls:
        if fc.name == "search_local_kb":
            args = fc.args or {}
            query = args.get("query", "") if isinstance(args, dict) else getattr(args, "query", "")
            print(f"\n[tool] search_local_kb: {query}")
            results = kb_service.search(str(query), top_k=3, min_score=0.25)
            context = _format_kb_results(results)
            await session.send(
                input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            name=fc.name,
                            id=fc.id,
                            response={"results": context},
                        )
                    ]
                )
            )


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(input, "message > ")
            if text.lower() == "q":
                break
            if self.session is not None:
                await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        import cv2
        import PIL.Image

        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_io.read()).decode()}

    async def get_frames(self):
        import cv2

        cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue is not None:
                await self.out_queue.put(frame)
        cap.release()

    def _get_screen(self):
        import mss
        import PIL.Image

        sct = mss.mss()
        monitor = sct.monitors[0]
        shot = sct.grab(monitor)
        image_bytes = mss.tools.to_png(shot.rgb, shot.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_io.read()).decode()}

    async def get_screen(self):
        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue is not None:
                await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            if self.session is not None:
                await self.session.send(input=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        kwargs = {"exception_on_overflow": False}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        while True:
            if self.session is None:
                await asyncio.sleep(0.05)
                continue
            turn = self.session.receive()
            async for response in turn:
                if response.tool_call:
                    await _handle_tool_call(self.session, response.tool_call)
                    continue
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="", flush=True)
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        if not os.environ.get("GEMINI_API_KEY"):
            print("Error: set GEMINI_API_KEY environment variable")
            sys.exit(1)

        kb_service._load_index()
        print(f"Loaded {len(kb_service.list_articles())} KB articles")
        print(f"Model: {MODEL}")
        print("Speak into the mic or type at message > (q to quit)\n")

        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")
        except asyncio.CancelledError:
            pass
        except ExceptionGroup as eg:
            if self.audio_stream is not None:
                self.audio_stream.close()
            traceback.print_exception(eg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        choices=["camera", "screen", "none"],
        help="Optional video stream (default: none)",
    )
    args = parser.parse_args()
    asyncio.run(AudioLoop(video_mode=args.mode).run())
