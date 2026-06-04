# Document Workflow System — Priority 1-3 Implementation

## Summary

Реализована полная система управления документами через цепочку агентов с тремя приоритетными функциями:

1. **Priority 1: Детальный просмотр документа** — модальное окно с полной историей
2. **Priority 2: Обратная связь** — возможность отправить правки назад к предыдущему агенту
3. **Priority 3: Архив и экспорт** — архивирование завершённых документов и скачивание истории

---

## Priority 1: Detailed Document View (Детализация)

### Что реализовано
- **Modal с полной историей** — при клике на документ в timeline открывается подробный вид
- **Структурированное отображение**:
  - Исходный материал (первые 2000 символов)
  - История всех этапов обработки
  - Для каждого этапа: агент, VERDICT, время, input, output
  - Лента правок (feedback chain)

### API Endpoints
```
GET /api/documents                    # Список активных и завершённых документов
GET /api/document/<doc_id>           # Полная история одного документа
```

### Frontend
- `openDocModal(docId)` — открыть модаль с документом
- `closeDocModal()` — закрыть модаль
- Кликабельные строки в timeline на /operator
- Hover эффект для визуальной обратной связи
- Responsive дизайн (макс 900px, 85vh высота)

### JavaScript
- Парсит полный workflow из API
- Рендерит каждый stage с временем (в локальной временной зоне)
- Показывает VERDICT badges (зелёный/оранжевый/синий)
- Наводит ссылку на агентов (имена переведены на русский)

---

## Priority 2: Backward Feedback Loop (Обратная связь)

### Что реализовано
- **Форма обратной связи** в modal с textarea
- **Отправка правок назад** — когда агент говорит `[VERDICT: needs_revision]`, оператор может отправить комментарии
- **Логика маршрутизации**:
  - Правки отправляются от последнего агента к предыдущему
  - Например: Marina → Rita (если Rita была перед Marina)
  - Хранятся в `feedback_chain[]`

### API Endpoints
```
POST /api/document/<doc_id>/feedback
  {
    "from_agent": "marina",
    "to_agent": "rita",
    "feedback": "Please fix section 3..."
  }
```

### Memory Storage
```python
doc["feedback_chain"] = [
  {
    "from_agent": "marina",
    "to_agent": "rita",
    "feedback": "Текст правок",
    "timestamp": "2026-06-04T02:07:12+00:00"
  }
]
```

### Frontend
- `toggleFeedbackBox()` — показать/скрыть форму
- `sendFeedback()` — отправить правки через API
- Textarea с описанием задачи
- Кнопки: "Отправить", "Отмена"

---

## Priority 3: Archive & Export (Архив и экспорт)

### Что реализовано

#### Archive
- Документ переходит из `in_progress` в `archived`
- Сохраняется `archived_at` timestamp
- API endpoint: `POST /api/document/<doc_id>/archive`

#### Export
- Скачивание полной истории в JSON
- Содержит:
  - Исходный файл (`original_content`)
  - Все stages с inputs/outputs
  - Feedback chain
  - Metadata (созданное время, статус, завершено)
- API endpoint: `POST /api/document/<doc_id>/export`
- Возвращает JSON файл с именем `{file_name}_history.json`

### Frontend
- Кнопка "📦 Архивировать" в modal
- Кнопка "⬇️ Скачать историю" в modal
- Подтверждение перед архивированием
- Обновление списка документов после архива

---

## Data Model

### Document Workflow Structure
```json
{
  "id": "8e7b4297",
  "file_name": "workbook_v1.md",
  "original_content": "Содержание файла (первые 2000 символов)",
  "created_at": "2026-06-04T02:07:30+00:00",
  "status": "in_progress|completed|archived",
  "archived_at": "2026-06-04T02:07:30+00:00",
  
  "stages": [
    {
      "agent": "victoria",
      "input": "Исходный текст",
      "output": "Отредактированный текст",
      "verdict": "ready_next|needs_revision|done",
      "timestamp": "2026-06-04T02:07:12+00:00"
    }
  ],
  
  "feedback_chain": [
    {
      "from_agent": "marina",
      "to_agent": "rita",
      "feedback": "Текст правок",
      "timestamp": "2026-06-04T02:07:12+00:00"
    }
  ],
  
  "current_stage": 1,
  "current_agent": "victoria"
}
```

---

## Flow Example

### Сценарий: Рабочая тетрадь через 3 агентов

1. **User** загружает файл → Victoria (editor)
2. **Victoria** редактирует → `[VERDICT: ready_next]` → Rita
3. **Rita** структурирует → `[VERDICT: ready_next]` → Marina
4. **Marina** проверяет маркетинг → `[VERDICT: needs_revision]`
5. **Operator** открывает modal, видит что Marina хочет правок
6. **Operator** кликает "Отправить правки назад", пишет коммент
7. **Rita** видит feedback и переделывает
8. **Rita** добавляет новый stage → `[VERDICT: done]`
9. **Status** меняется на `completed`
10. **Operator** архивирует документ
11. **Operator** скачивает JSON со всей историей

---

## File Changes

### memory.py
```python
# Новые функции:
add_backward_feedback(doc_id, from_agent, to_agent, feedback)  # Отправить правки
archive_document(doc_id)                                        # Архивировать
export_document(doc_id)                                         # Экспортировать
```

### webapp.py
```python
# Новые endpoints:
POST /api/document/<doc_id>/feedback   # Отправить обратную связь
POST /api/document/<doc_id>/archive    # Архивировать документ
POST /api/document/<doc_id>/export     # Экспортировать историю (JSON)

# JavaScript функции:
openDocModal(docId)      # Открыть modal
closeDocModal()          # Закрыть modal
toggleFeedbackBox()      # Показать/скрыть форму
sendFeedback()           # Отправить правки
archiveDoc()             # Архивировать
exportDoc()              # Экспортировать
```

### CSS
- `.docModal` — стили для модального окна
- `.docModalContent` — контент modal
- `.docStage` — стиль этапа обработки
- `.feedbackBox` — форма обратной связи
- `.docActions` — кнопки действий

---

## Testing

Проведён интеграционный тест со следующими проверками:
- ✓ Создание workflow
- ✓ Добавление stages
- ✓ Добавление feedback
- ✓ Архивирование документа
- ✓ Экспорт истории
- ✓ Список документов по статусу

Тест: `test_document_workflow.py` (выполнен успешно, удалён)

---

## Использование

### Для пользователя
1. Загрузить файл в Victoria
2. Пройти через цепочку агентов
3. Открыть modal на /operator странице при клике на документ
4. Посмотреть полную историю
5. Отправить правки если нужны через кнопку "Отправить правки назад"
6. Архивировать завершённый документ
7. Скачать историю в JSON для архива

### Для разработчика
- API полностью функционален
- Все endpoints возвращают JSON
- CSRF защита включена
- Atomic write операции (безопасно для параллельного доступа)

---

## Future Enhancements

Возможные улучшения (не реализованы):
- [ ] Версионирование с diff (side-by-side сравнение)
- [ ] Выбор целевого агента при отправке правок (сейчас автоматически)
- [ ] Сохранение черновиков документов
- [ ] История изменения статусов (timeline)
- [ ] Notifications при получении feedback
- [ ] Bulk operations (архивировать несколько документов)
- [ ] Search по документам

---

## Commit History

- `d78127f` — Document workflow: Priority 1-3 implementation
  - Priority 1: Detailed document view modal
  - Priority 2: Backward feedback loop
  - Priority 3: Archive & Export
  - 302 insertions, 1 deletion
