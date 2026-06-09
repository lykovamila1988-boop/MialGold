# Marina: Context Examples & from_agent Usage

## What is Context?

When Marina (or any agent) receives a request, it can come from:
1. **User directly** — "Create 5 posts for this week"
2. **Another agent** — Victoria (editor) processed content, now Marina needs marketing strategy
3. **Part of a workflow chain** — Olya found trends, Marina creates content, Victoria edits it

Context helps Marina understand **who sent the request** and **who will use the result**.

---

## Format of Context Tags

### Basic Format

```
[from: <agent>] [to: <agent>] [chain_id: <id>]
```

- `from: <agent>` — who sent this request (victoria, olya, dima, etc.)
- `to: <agent>` — who will receive the result (optional)
- `chain_id: <id>` — unique workflow identifier (optional)

### Examples

**Example 1: User direct request (no tags needed)**
```
"Проанализируй статистику постов"
```
→ Context: `{from_agent: 'user'}`

**Example 2: Victoria (editor) processed content**
```
"[from: victoria] Отредактировала 5 постов про выбор в отношениях. Какая стратегия для каждого?"
```
→ Context: `{from_agent: 'victoria'}`

**Example 3: Olya (trends) + chain tracking**
```
"[from: olya] [chain_id: week_2026_06_08] Выявила 3 тренда: тревога, отношения, вина. Сделай контент."
```
→ Context: `{from_agent: 'olya', chain_id: 'week_2026_06_08'}`

**Example 4: Dima (sales) → result to Victoria (editor)**
```
"[from: dima] [to: victoria] Вот топ-продаваемые темы за неделю: привязанность, доверие, выбор."
```
→ Context: `{from_agent: 'dima', to_agent: 'victoria'}`

---

## How to Extract & Use Context in `handle()`

### Basic Pattern: Extract Context

```python
def handle(name: str, inputs: dict) -> str:
    # Extract context if provided
    context = inputs.get('_context', {})
    from_agent = context.get('from_agent', 'user')
    to_agent = context.get('to_agent')
    chain_id = context.get('chain_id')

    # Now use it
    if from_agent != 'user':
        console.print(f"[yellow]Request from {from_agent}[/yellow]")

    return run_tool(name, inputs)
```

### Practical Example: Adjust Behavior Based on from_agent

```python
def handle(name: str, inputs: dict) -> str:
    context = inputs.get('_context', {})
    from_agent = context.get('from_agent', 'user')

    # Different behavior based on who sent the request
    if from_agent == 'victoria':
        # Victoria = text is already edited, focus on marketing strategy
        console.print("[cyan]Victoria processed text → ready for strategy[/cyan]")

    elif from_agent == 'olya':
        # Olya = trends analysis, build content on these trends
        console.print("[cyan]Olya found trends → ready for content creation[/cyan]")

    elif from_agent == 'dima':
        # Dima = sales data, focus on what converts
        console.print("[cyan]Dima has sales data → ready for data-driven strategy[/cyan]")

    return run_tool(name, inputs)
```

### Advanced: Log Chain Processing

```python
def handle(name: str, inputs: dict) -> str:
    context = inputs.get('_context', {})
    from_agent = context.get('from_agent', 'user')
    to_agent = context.get('to_agent')
    chain_id = context.get('chain_id')

    # Log the flow
    if chain_id:
        flow = f"{from_agent} → marina"
        if to_agent:
            flow += f" → {to_agent}"
        console.print(f"[dim]Chain {chain_id}: {flow}[/dim]")

    return run_tool(name, inputs)
```

---

## Real Workflow Scenarios

### Scenario A: Victoria (Editor) → Marina (Marketer)

**Victoria's message to Marina:**
```
[from: victoria] [chain_id: week_2026_06_08]
Отредактировала 5 постов про выбор. Готовы к публикации по качеству текста.
```

**Marina understands:**
- `from_agent='victoria'` → text is already editor-approved
- Can focus on: marketing hook, CTA, hashtag strategy
- Don't waste time on grammar/spelling — Victoria checked that
- Result goes to publication/Instagram

**Marina's response (in handle()):**
```python
def handle(name: str, inputs: dict) -> str:
    context = inputs.get('_context', {})
    
    if context.get('from_agent') == 'victoria':
        # Victoria already made sure text is perfect
        # → Focus on marketing strategy (hooks, CTAs, reach)
        console.print("[green]Text approved by Victoria → pure strategy mode[/green]")

    return run_tool(name, inputs)
```

---

### Scenario B: Olya (Trends) → Marina (Marketer) → Victoria (Editor)

**Olya's message:**
```
[from: olya] [to: victoria] [chain_id: week_2026_06_08]
Выявила тренды: тревога привязанности, страх выбора, вина в отношениях.
```

**Marina understands:**
- `from_agent='olya'` → these are research-backed trends
- `to_agent='victoria'` → final result goes to Victoria for editing
- Chain_id tracks the entire week's workflow
- Marina's job: create killer content hooks based on these trends

**Marina's response:**
```python
def handle(name: str, inputs: dict) -> str:
    context = inputs.get('_context', {})
    from_agent = context.get('from_agent')
    to_agent = context.get('to_agent')

    if from_agent == 'olya' and to_agent == 'victoria':
        # Olya researched → I create → Victoria edits
        # → Create content optimized for editing (clear structure, points for hooks)
        console.print("[green]Olya→Marina→Victoria pipeline detected[/green]")

    return run_tool(name, inputs)
```

---

### Scenario C: Dima (Sales) → Marina (Marketer) → Audience

**Dima's message:**
```
[from: dima] [chain_id: week_2026_06_08]
Продажи за неделю: 12 consultations, $1440. Топ-тема: привязанность + выбор.
```

**Marina understands:**
- `from_agent='dima'` → hard data on what converts
- `to_agent` not specified → result goes directly to audience
- Chain_id lets Marina track: when did Dima report? what was sold?
- Marina's job: capitalize on what converts with a new post

**Marina's response:**
```python
def handle(name: str, inputs: dict) -> str:
    context = inputs.get('_context', {})
    from_agent = context.get('from_agent')
    chain_id = context.get('chain_id')

    if from_agent == 'dima':
        # Dima = sales data → what actually converts
        # → Create content that amplifies top-selling topics
        console.print(f"[cyan]Dima's sales data (chain {chain_id}) → amplify top-sellers[/cyan]")

    return run_tool(name, inputs)
```

---

## How Context Flows Through run_agent()

When you call `run_agent()` with context, the base system automatically:

1. **Extracts context tags** from the user message
2. **Updates system prompt** with context info
3. **Passes it to Claude** so Marina understands the workflow

### Usage:

```python
# Direct call with context dict
context = {
    'from_agent': 'victoria',
    'chain_id': 'week_2026_06_08'
}
run_agent("Проанализируй эти посты", [], context=context)
```

### What Marina sees in system prompt:

```
=== КОНТЕКСТ ЗАПРОСА ===
✓ Ты получила запрос от: victoria
✓ ID цепочки обработки: week_2026_06_08
✓ Твоя позиция в цепочке: #2
✓ Следующий агент: Victoria

=== КАК ДЕЙСТВОВАТЬ ===
Запрос пришел от Victoria. Её работа требует твоей обработки.
После твоей работы результат пойдет Victoria — подготавливай под её требования.
Все сообщения связаны ID 'week_2026_06_08' — это помогает отслеживать работу.
```

---

## Checklist: When to Use Context

- [ ] **Use context tags** when Marina receives work from another agent
- [ ] **Include chain_id** when this is part of a multi-step workflow
- [ ] **Add to_agent** when the result goes to someone other than Marina's caller
- [ ] **Extract in handle()** to adjust tool behavior based on source agent
- [ ] **Log the flow** for debugging (who→Marina→who)

---

## Quick Reference

| Scenario | Tag Format | Marina's Focus |
|----------|-----------|-----------------|
| User → Marina | (no tag) | Full context analysis |
| Victoria → Marina | `[from: victoria]` | Strategy only (text approved) |
| Olya → Marina → Victoria | `[from: olya] [to: victoria]` | Trends-based, editable format |
| Dima → Marina | `[from: dima]` | Data-driven strategy |
| Chain tracking | `[chain_id: week_...]` | Log to correlate steps |

