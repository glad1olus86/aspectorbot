"""Шаблоны сообщений для бота."""


def get_start_message_private() -> str:
    """
    Получить приветственное сообщение для личного чата.

    Returns:
        Текст сообщения /start
    """
    return """👋 Привет! Я Aspector STT — бот для расшифровки голосовых сообщений.

🎙️ Просто отправь мне голосовое, и я переведу его в текст.
Язык определяется автоматически (Whisper)."""


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
2. Я автоматически определю язык и расшифрую

**Команды:**
/start — Запустить бота
/help — Эта справка"""


def get_success_message(
    text: str, lang: str, processing_time: float
) -> str:
    """
    Получить сообщение с результатом распознавания.

    Args:
        text: Распознанный текст
        lang: Код языка (из Whisper)
        processing_time: Время обработки в секундах

    Returns:
        Текст сообщения с расшифровкой
    """
    lang_info = f"🌍 Язык: {lang}" if lang else ""

    return f"""🎤 Расшифровка ГС:

{text}

{lang_info}
⏱️ Время обработки: {processing_time:.1f} сек"""


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


def get_trello_card_message(
    title: str, description: str, deadline: str | None = None, assignee: str | None = None
) -> str:
    """
    Получить сообщение с готовой задачей.

    Args:
        title: Заголовок задачи
        description: Описание задачи
        deadline: Дедлайн (строка) или None
        assignee: @username исполнителя или None

    Returns:
        Текст сообщения с задачей
    """
    extra = ""
    if assignee:
        extra += f"\n👷 <b>Исполнитель:</b> {assignee}"
    if deadline:
        extra += f"\n⏰ <b>Дедлайн:</b> {deadline}"
    return f"""📋 Задача:

<b>Тема:</b> {title}

<b>Описание:</b>
{description}{extra}"""


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


# ─── Сообщения для групповых задач ──────────────────────────────────────


def get_group_task_pending_message(
    title: str,
    description: str,
    creator_username: str | None,
    deadline: str | None = None,
    assignee: str | None = None,
) -> str:
    """Сообщение задачи в группе — статус: ожидает."""
    author = f"@{creator_username}" if creator_username else "Неизвестный"
    mention = f"{assignee}, тебе задача!\n\n" if assignee else ""
    assignee_line = f"\n👷 Назначено: {assignee}" if assignee else ""
    deadline_line = f"\n⏰ Дедлайн: {deadline}" if deadline else ""
    return f"""{mention}📋 <b>Задача</b>

<b>Тема:</b> {title}

<b>Описание:</b>
{description}

━━━━━━━━━━━━━━━━
⏳ <b>Статус:</b> Ожидает

👤 Автор: {author}{assignee_line}{deadline_line}"""


def get_group_task_in_progress_message(
    title: str,
    description: str,
    creator_username: str | None,
    worker_username: str | None,
    deadline_str: str,
) -> str:
    """Сообщение задачи в группе — статус: в работе."""
    author = f"@{creator_username}" if creator_username else "Неизвестный"
    worker = f"@{worker_username}" if worker_username else "Неизвестный"
    return f"""📋 <b>Задача</b>

<b>Тема:</b> {title}

<b>Описание:</b>
{description}

━━━━━━━━━━━━━━━━
🔵 <b>Статус:</b> В работе

👤 Автор: {author}
👷 Исполнитель: {worker}
⏰ Дедлайн: {deadline_str}"""


def get_group_task_done_message(
    title: str,
    description: str,
    creator_username: str | None,
    worker_username: str | None,
    completed_str: str,
) -> str:
    """Сообщение задачи в группе — статус: выполнено."""
    author = f"@{creator_username}" if creator_username else "Неизвестный"
    worker = f"@{worker_username}" if worker_username else "Неизвестный"
    return f"""📋 <b>Задача</b>

<b>Тема:</b> {title}

<b>Описание:</b>
{description}

━━━━━━━━━━━━━━━━
✅ <b>Статус:</b> Выполнено

👤 Автор: {author}
👷 Исполнитель: {worker}
🕐 Выполнено: {completed_str}"""


def get_task_completed_dm_message(
    title: str,
    worker_username: str | None,
    completed_str: str,
) -> str:
    """Уведомление автору в ЛС о выполнении задачи."""
    worker = f"@{worker_username}" if worker_username else "Неизвестный"
    return f"""✅ <b>Задача выполнена!</b>

<b>Тема:</b> {title}

👷 Выполнил: {worker}
🕐 Время: {completed_str}"""


__all__ = [
    "get_start_message_private",
    "get_start_message_group",
    "get_help_message",
    "get_success_message",
    "get_error_message",
    "get_queue_message",
    "get_processing_message",
    "get_trello_generating_message",
    "get_trello_card_message",
    "get_trello_edit_prompt_message",
    "get_trello_created_message",
    "get_trello_error_message",
    "get_trello_cancelled_message",
    "get_group_task_pending_message",
    "get_group_task_in_progress_message",
    "get_group_task_done_message",
    "get_task_completed_dm_message",
]
