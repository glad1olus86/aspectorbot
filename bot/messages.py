"""Шаблоны сообщений для бота."""

from config import config


def get_start_message_private() -> str:
    """
    Получить приветственное сообщение для личного чата.

    Returns:
        Текст сообщения /start
    """
    languages = config.SUPPORTED_LANGUAGES
    flags = config.LANGUAGE_FLAGS

    lang_list = " · ".join(
        f"{flags.get(code, '')} {name}" for code, name in languages.items()
    )

    return f"""👋 Привет! Я Aspector STT — бот для расшифровки голосовых сообщений.

🎙️ Просто отправь мне голосовое, и я переведу его в текст.
Поддерживаю: {lang_list}

Язык определяется автоматически."""


def get_start_message_group() -> str:
    """
    Получить приветственное сообщение для группового чата.

    Returns:
        Краткий текст сообщения /start для группы
    """
    return """👋 Aspector STT активен в этом чате!
🎙️ Отправляйте голосовые — расшифрую автоматически."""


def get_help_message() -> str:
    """
    Получить сообщение помощи.

    Returns:
        Текст сообщения /help
    """
    return """ℹ️ **Aspector STT — Помощь**

Я умею распознавать голосовые сообщения и переводить их в текст.

**Как использовать:**
1. Отправьте мне голосовое сообщение
2. Я автоматически определю язык
3. Отправлю вам текстовую расшифровку

**Если язык не определился:**
• Я отправлю кнопки с выбором языка
• Нажать может любой участник чата
• После выбора я расшифрую сообщение

**Поддерживаемые языки:**
🇷🇺 Русский
🇺🇸 English
🇺🇦 Українська
🇨🇿 Čeština

**Команды:**
/start — Запустить бота
/help — Эта справка
/lang — Выбрать язык (пропускает автоопределение)

Работаю полностью офлайн — ваши данные не отправляются на сторонние серверы."""


def get_success_message(
    text: str, lang: str, processing_time: float, manual: bool = False, username: str | None = None
) -> str:
    """
    Получить сообщение с результатом распознавания.

    Args:
        text: Распознанный текст
        lang: Код языка
        processing_time: Время обработки в секундах
        manual: Был ли язык выбран вручную
        username: Username пользователя который выбрал язык

    Returns:
        Текст сообщения с расшифровкой
    """
    languages = config.SUPPORTED_LANGUAGES
    flags = config.LANGUAGE_FLAGS

    lang_name = languages.get(lang, lang)
    flag = flags.get(lang, "")

    if manual:
        lang_info = f"✅ Язык выбран вручную: {flag} {lang_name}"
        if username:
            lang_info += f" (выбрал @{username})"
    else:
        lang_info = f"🌍 Язык определён автоматически: {flag} {lang_name}"

    return f"""🎤 Расшифровка ГС:

{text}

{lang_info}
⏱️ Время обработки: {processing_time:.1f} сек"""


def get_pending_language_message() -> str:
    """
    Получить сообщение когда не удалось определить язык.

    Returns:
        Текст сообщения с просьбой выбрать язык
    """
    return """🤔 Не удалось автоматически определить язык голосового.

Выберите язык — и я расшифрую:"""


def get_language_selected_message(username: str | None = None) -> str:
    """
    Получить сообщение после выбора языка (для редактирования).

    Args:
        username: Username пользователя который выбрал язык

    Returns:
        Текст сообщения с подтверждением выбора
    """
    base = "🤔 Не удалось автоматически определить язык голосового.\n\n"

    if username:
        return f"{base}✅ Язык выбран: @{username}"
    else:
        return f"{base}✅ Язык выбран"


def get_error_message() -> str:
    """
    Получить сообщение об ошибке распознавания.

    Returns:
        Текст сообщения об ошибке
    """
    return """😕 Не удалось распознать речь в этом голосовом.

Возможные причины:
• Слишком много шума в записи
• Очень короткое или тихое сообщение
• Язык не входит в список поддерживаемых

Попробуй записать ещё раз."""


def get_queue_message(position: int) -> str:
    """
    Получить сообщение о позиции в очереди.

    Args:
        position: Позиция в очереди

    Returns:
        Текст сообщения о очереди
    """
    return f"""⏳ Голосовое получено, поставлено в очередь.
Позиция: {position} — обработаю как только освобожусь!"""


def get_processing_message() -> str:
    """
    Получить сообщение о начале обработки.

    Returns:
        Текст сообщения о обработке
    """
    return "🎧 Обрабатываю голосовое сообщение..."


def get_trello_generating_message() -> str:
    """
    Получить сообщение о генерации задачи через Gemini.

    Returns:
        Текст сообщения о генерации
    """
    return "🤖 Формирую задачу..."


def get_trello_card_message(title: str, description: str) -> str:
    """
    Получить сообщение с готовой задачей.

    Args:
        title: Заголовок задачи
        description: Описание задачи

    Returns:
        Текст сообщения с задачей
    """
    return f"""📋 Задача:

<b>Тема:</b> {title}

<b>Описание:</b>
{description}"""


def get_trello_edit_prompt_message() -> str:
    """
    Получить сообщение с просьбой ввести правки.

    Returns:
        Текст сообщения с просьбой ввести правки
    """
    return """✏️ Напишите или отправьте голосовое сообщение, какие правки нужно внести в задачу.

Опишите кратко, что изменить в заголовке или описании."""


def get_trello_created_message(card_url: str, card_name: str, photo_count: int = 0) -> str:
    """
    Получить сообщение об успешном создании карточки.

    Args:
        card_url: Ссылка на карточку
        card_name: Название карточки
        photo_count: Количество прикреплённых фотографий

    Returns:
        Текст сообщения об успехе
    """
    photo_line = f"\n📎 Прикреплено фото: {photo_count}" if photo_count > 0 else ""
    return f"""✅ Карточка создана в Trello!

<b>Название:</b> {card_name}
<b>Ссылка:</b> <a href="{card_url}">Открыть карточку</a>{photo_line}"""


def get_trello_cancelled_message() -> str:
    """
    Получить сообщение об отмене создания карточки Trello.

    Returns:
        Текст сообщения об отмене
    """
    return "❌ Создание карточки в Trello отменено."


def get_trello_error_message() -> str:
    """
    Получить сообщение об ошибке при формировании задачи.

    Returns:
        Текст сообщения об ошибке
    """
    return """😕 Не удалось сформировать задачу.

Возможные причины:
• Ошибка API
• Проблема с настройками
• Ошибка при генерации через Gemini

Попробуйте ещё раз или обратитесь к администратору."""


__all__ = [
    "get_start_message_private",
    "get_start_message_group",
    "get_help_message",
    "get_success_message",
    "get_pending_language_message",
    "get_language_selected_message",
    "get_error_message",
    "get_queue_message",
    "get_processing_message",
    "get_trello_generating_message",
    "get_trello_card_message",
    "get_trello_edit_prompt_message",
    "get_trello_created_message",
    "get_trello_error_message",
    "get_trello_cancelled_message",
]
