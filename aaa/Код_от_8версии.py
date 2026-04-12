import os
import requests
import json
import re
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel, Field

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class Pipe:
    class Valves(BaseModel):
        MWS_API_KEY: str = Field(default="ключ")
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
        self.id = "gpthub_ultimate_conveyor_v6_fixed"
        self.name = "GPTHub Ultimate Router v6.1 (Cleaned) 🚀"

    def _fetch_web_page(self, url: str) -> str:
        try:
            res = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=10,
            )
            if BeautifulSoup:
                soup = BeautifulSoup(res.text, "html.parser")
                for script in soup(["script", "style"]):
                    script.extract()
                return soup.get_text(separator=" ", strip=True)[:8000]
            else:
                text = re.sub(
                    r"<style.*?</style>", "", res.text, flags=re.DOTALL | re.IGNORECASE
                )
                text = re.sub(
                    r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE
                )
                text = re.sub(r"<[^>]+>", " ", text)
                return " ".join(text.split())[:8000]
        except Exception as e:
            return f"[Ошибка парсинга {url}: {str(e)}]"

    def _search_web(self, query: str) -> str:
        try:
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(url, headers=headers, timeout=10)
            if BeautifulSoup:
                soup = BeautifulSoup(res.text, "html.parser")
                results = [
                    a.get_text(strip=True)
                    for a in soup.find_all("a", class_="result__snippet", limit=5)
                ]
            else:
                results = re.findall(
                    r'class="result__snippet[^>]*>(.*?)</a>', res.text, re.IGNORECASE
                )
                results = [re.sub(r"<[^>]+>", "", r) for r in results][:5]
            return (
                "\n".join([f"- {r}" for r in results])
                if results
                else "[Ничего не найдено. Возможно, стоит уточнить запрос.]"
            )
        except Exception as e:
            return f"[Ошибка поиска: {str(e)}]"

    # === ФИКС БАГА 3 (Мусор в промптах): Усиленная очистка ===
    def _clean_junk(self, text: str) -> str:
        if not text:
            return ""
        # Удаляем блоки с контентом и источниками вместе с их содержимым
        text = re.sub(r"<(context|source)[\s\S]*?</\1>", "", text)
        text = re.sub(r"</?(context|source)[^>]*>", "", text)

        # Агрессивное удаление системных RAG-инструкций Open WebUI
        if "### Task:" in text:
            if "Output:" in text:
                text = text.split("Output:")[-1]
            else:
                # Если интерфейс не поставил Output:, отрезаем всю "шапку" вплоть до конца дурацкой инструкции
                text = re.sub(
                    r"### Task:[\s\S]*?(incorporating inline citations|\[id\])[^\n]*\n",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )

        # Чистим артефакты, если остались звездочки
        text = text.replace("*### Task:", "").replace("*...", "")
        return text.strip()

    def _get_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                [i.get("text", "") for i in content if i.get("type") == "text"]
            )
        return ""

    def _ask_vision_internally(self, valves, messages, system_instruction):
        headers = {
            "Authorization": f"Bearer {valves.MWS_API_KEY}",
            "Content-Type": "application/json",
        }
        last_msg_content = messages[-1]["content"]
        payload_messages = messages[:-1] + [
            {"role": "user", "content": last_msg_content}
        ]

        payload = {
            "model": valves.VISION_MODEL,
            "messages": payload_messages,
            "temperature": 0.2,
        }

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
        raw_text = self._get_text(messages[-1].get("content", ""))
        text = self._clean_junk(raw_text)

        if not text:
            return "TEXT"

        system_prompt = "Classify intent into ONE word: IMAGE (draw), CODE (programming), SEARCH (news), TEXT (other)."
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

        has_img = (
            any(i.get("type") == "image_url" for i in last_content)
            if isinstance(last_content, list)
            else False
        )

        intent = self.classify_intent(valves, messages)
        raw_text = self._get_text(last_content)
        user_prompt_clean = self._clean_junk(raw_text)

        # === Сбор дополнительного контекста (Поиск, Веб, Файлы) ===
        extra_context = ""
        urls = re.findall(r"(https?://[^\s]+)", user_prompt_clean)
        has_files = "<context>" in raw_text

        if urls:
            extra_context += (
                f"\n\n[Контент со страницы {urls[0]}]:\n{self._fetch_web_page(urls[0])}"
            )
            intent = "SEARCH"
        elif intent == "SEARCH":
            extra_context += (
                f"\n\n[Данные из поиска]:\n{self._search_web(user_prompt_clean)}"
            )
        elif has_files:
            file_matches = re.findall(
                r"<(context|source).*?>(.*?)</\1>", raw_text, flags=re.DOTALL
            )
            for _, file_text in file_matches:
                extra_context += (
                    f"\n\n[Содержимое прикрепленного файла]:\n{file_text.strip()}"
                )

        # === ЛОГИКА 1: РИСОВАНИЕ ===
        if intent == "IMAGE":

            def img_pipeline():
                prompt = user_prompt_clean
                if has_img:
                    yield "🔍 Изучаю референс...\n\n"
                    desc = self._ask_vision_internally(
                        valves, messages, "Describe image for generation."
                    )
                    prompt = f"{desc}. Style: {user_prompt_clean}"

                yield f"🎨 Генерирую изображение: *{user_prompt_clean}*...\n\n"
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
                    yield f"![Result]({url})\n\n---\n> **Pipeline:** IMAGE"
                except:
                    yield f"❌ Ошибка: {res.text}"

            return img_pipeline()

        # === ВЫБОР МОДЕЛИ ===
        if intent == "CODE" and has_img:
            body["model"] = valves.VISION_MODEL
        elif not has_img:
            mapping = {
                "CODE": valves.CODE_MODEL,
                "SEARCH": valves.SEARCH_MODEL,
                "TEXT": valves.TEXT_MODEL,
            }
            body["model"] = mapping.get(intent, valves.TEXT_MODEL)
        else:
            body["model"] = valves.VISION_MODEL

        # === ФИКС БАГА 2: ВСЕГДА ЧИСТИМ ИСТОРИЮ (в т.ч. для SEARCH) ===
        clean_messages = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                new_content = []
                for item in content:
                    if item.get("type") == "text":
                        cleaned = self._clean_junk(item.get("text", ""))
                        if cleaned:
                            new_content.append({"type": "text", "text": cleaned})
                    elif item.get("type") == "image_url":
                        # Оставляем картинки ТОЛЬКО если выбрана Vision-модель! Иначе DeepSeek падает.
                        if body["model"] == valves.VISION_MODEL:
                            new_content.append(item)

                # Если после чистки остался контент, добавляем
                if new_content:
                    clean_messages.append({"role": m["role"], "content": new_content})
            else:
                cleaned_text = self._clean_junk(content)
                if cleaned_text:
                    clean_messages.append({"role": m["role"], "content": cleaned_text})

        body["messages"] = clean_messages

        # === ФИКС БАГА 1: Не подшиваем файлы/поиск к генерации картинок ===
        if extra_context and intent != "IMAGE" and len(body["messages"]) > 0:
            last_msg = body["messages"][-1]
            if isinstance(last_msg.get("content"), list):
                text_added = False
                for item in last_msg["content"]:
                    if item.get("type") == "text":
                        item["text"] += extra_context
                        text_added = True
                        break
                if not text_added:
                    last_msg["content"].append({"type": "text", "text": extra_context})
            else:
                last_msg["content"] += extra_context

        footer = f"\n\n---\n> **GPTHub Core:** {body['model']}"
        return self.stream_response(
            valves.MWS_BASE_URL, valves.MWS_API_KEY, body, footer
        )

    def stream_response(self, url, key, body, footer):
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            with requests.post(
                f"{url}/chat/completions", headers=headers, json=body, stream=True
            ) as r:
                if r.status_code != 200:
                    yield f"❌ **Ошибка API:** {r.text}"
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
            yield f"Ошибка: {str(e)}"

