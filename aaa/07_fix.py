import os
import requests
import json
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        MWS_API_KEY: str = Field(default="sk-ewgiaPC3A6pPDYHwR8siVA")
        MWS_BASE_URL: str = Field(default="https://api.gpt.mws.ru/v1")

        # Модели
        ROUTER_MODEL: str = Field(default="gemma-3-27b-it")
        TEXT_MODEL: str = Field(default="Qwen3-235B-A22B-Instruct-2507-FP8")
        VISION_MODEL: str = Field(default="qwen2.5-vl-72b")
        CODE_MODEL: str = Field(default="qwen3-coder-480b-a35b")
        SEARCH_MODEL: str = Field(default="deepseek-r1-distill-qwen-32b")
        IMAGE_MODEL: str = Field(default="qwen-image-lightning")

    def __init__(self):
        self.type = "pipe"
        self.id = "gpthub_ultimate_conveyor_v6"
        self.name = "GPTHub Ultimate Router v6.0 🚀"

    def _get_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                [i.get("text", "") for i in content if i.get("type") == "text"]
            )
        return ""

    def _ask_vision_internally(self, valves, messages, system_instruction):
        """Внутренний вызов 'глаз' для анализа контекста перед основным действием."""
        headers = {
            "Authorization": f"Bearer {valves.MWS_API_KEY}",
            "Content-Type": "application/json",
        }

        # Важно: копируем сообщения, чтобы не испортить оригинал
        payload_messages = messages[:-1] + [
            {"role": "user", "content": messages[-1]["content"]}
        ]

        payload = {
            "model": valves.VISION_MODEL,
            "messages": payload_messages,
            "temperature": 0.2,
        }

        # Вставляем инструкцию в контент последнего сообщения
        if isinstance(payload["messages"][-1]["content"], list):
            for item in payload["messages"][-1]["content"]:
                if item["type"] == "text":
                    item["text"] = system_instruction

        try:
            res = requests.post(
                f"{valves.MWS_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            return res.json()["choices"][0]["message"]["content"]
        except:
            return ""

    def classify_intent(self, valves, messages) -> str:
        text = self._get_text(messages[-1].get("content", ""))
        if not text:
            return "TEXT"

        system_prompt = (
            "Classify intent into ONE word:\n"
            "IMAGE: Draw/Generate/Style new image.\n"
            "CODE: Write code, HTML from mockup, SQL, diagrams.\n"
            "SEARCH: Real-time info, news.\n"
            "TEXT: Everything else."
        )
        try:
            res = requests.post(
                f"{valves.MWS_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {valves.MWS_API_KEY}"},
                json={
                    "model": valves.ROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 5,
                },
            )
            intent = res.json()["choices"][0]["message"]["content"].upper()
            return next(
                (tag for tag in ["IMAGE", "CODE", "SEARCH"] if tag in intent), "TEXT"
            )
        except:
            return "TEXT"

    def pipe(
        self, body: dict, __user__: dict, __task__: str = None
    ) -> Union[str, Generator, Iterator]:
        valves = self.Valves(**body.get("valves", {}))
        messages = body.get("messages", [])
        last_content = messages[-1].get("content", "")

        # 1. Есть ли картинка?
        has_img = (
            any(i.get("type") == "image_url" for i in last_content)
            if isinstance(last_content, list)
            else False
        )

        # 2. Что хочет юзер?
        intent = self.classify_intent(valves, messages)
        user_prompt = self._get_text(last_content)

        # === ЛОГИКА 1: РИСОВАНИЕ (IMAGE) ===
        if intent == "IMAGE":

            def img_pipeline():
                prompt = user_prompt
                if has_img:
                    yield "🔍 Изучаю референс своим зрением...\n\n"
                    desc = self._ask_vision_internally(
                        valves,
                        messages,
                        "Опиши объекты на фото максимально детально для генерации похожей картинки. Не упоминай стиль.",
                    )
                    prompt = f"{desc}. Style: {user_prompt}" if desc else user_prompt

                yield f"🎨 Генерирую новое изображение по запросу: *{user_prompt}*...\n\n"
                res = requests.post(
                    f"{valves.MWS_BASE_URL}/images/generations",
                    headers={"Authorization": f"Bearer {valves.MWS_API_KEY}"},
                    json={
                        "model": valves.IMAGE_MODEL,
                        "prompt": prompt,
                        "size": "1024x1024",
                    },
                )
                try:
                    url = res.json()["data"][0]["url"]
                    yield f"![Result]({url})\n\n---\n> **Pipeline:** {valves.VISION_MODEL if has_img else ''} -> {valves.IMAGE_MODEL}"
                except:
                    yield f"❌ Ошибка генерации: {res.text}"

            return img_pipeline()

        # === ВЫБОР МОДЕЛИ И ФУТЕРА ===
        if intent == "CODE" and has_img:
            body["model"] = valves.VISION_MODEL
            footer = f"\n\n---\n> **GPTHub Vision-Coder:** Использована `{valves.VISION_MODEL}`"
        elif not has_img:
            mapping = {
                "CODE": valves.CODE_MODEL,
                "SEARCH": valves.SEARCH_MODEL,
                "TEXT": valves.TEXT_MODEL,
            }
            body["model"] = mapping.get(intent, valves.TEXT_MODEL)
            footer = f"\n\n---\n> **GPTHub Router:** Модель `{body['model']}`"
        else:
            body["model"] = valves.VISION_MODEL
            footer = f"\n\n---\n> **GPTHub Vision:** Модель `{valves.VISION_MODEL}`"

        # === КРИТИЧЕСКИЙ ФИКС: Очистка истории от картинок для текстовых моделей ===
        if body["model"] != valves.VISION_MODEL:
            clean_messages = []
            for m in messages:
                content = m.get("content", "")
                if isinstance(content, list):
                    # Извлекаем только текстовую часть из мультимодального сообщения
                    only_text = " ".join(
                        [
                            item.get("text", "")
                            for item in content
                            if item.get("type") == "text"
                        ]
                    )
                    clean_messages.append({"role": m["role"], "content": only_text})
                else:
                    clean_messages.append({"role": m["role"], "content": content})
            body["messages"] = clean_messages

        # Финальный стриминг
        return self.stream_response(
            valves.MWS_BASE_URL, valves.MWS_API_KEY, body, footer
        )

    def stream_response(self, url, key, body, footer):
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            with requests.post(
                f"{url}/chat/completions", headers=headers, json=body, stream=True
            ) as r:
                # Обработка ошибок API (400, 401, 500 и т.д.)
                if r.status_code != 200:
                    yield f"❌ **Ошибка MWS API ({r.status_code}):** {r.text}"
                    return

                for line in r.iter_lines():
                    if line:
                        line = line.decode("utf-8").replace("data: ", "")
                        if line == "[DONE]":
                            break
                        try:
                            content = json.loads(line)["choices"][0]["delta"].get(
                                "content", ""
                            )
                            yield content
                        except:
                            continue
                yield footer
        except Exception as e:
            yield f"Ошибка соединения: {str(e)}"
