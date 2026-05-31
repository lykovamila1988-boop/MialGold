import { useState } from "react";

const T = '#C4614A'; // terra
const N = '#1E140F'; // night
const C = '#FAF6F1'; // cream
const M = '#F2EAE2'; // mist
const U = '#7A5E54'; // muted
const B = '#E0D0C8'; // border
const W = '#FFFFFF'; // white
const G = '#4a7a5e'; // green

// ─── DATA ────────────────────────────────────────────────

const SECTIONS = [
  { id: 'overview',    label: '🏛 Обзор',         icon: '🏛' },
  { id: 'flow',        label: '🔄 Как работает',   icon: '🔄' },
  { id: 'agents',      label: '👥 Агенты',         icon: '👥' },
  { id: 'tools',       label: '🔧 Инструменты',    icon: '🔧' },
  { id: 'folder',      label: '📁 Папка',          icon: '📁' },
  { id: 'startup',     label: '🚀 Запуск',         icon: '🚀' },
];

const AGENTS = [
  { emoji:'📣', name:'Марина',   role:'Маркетолог',       file:'agent.py',    color:T,
    knows:['Instagram API','Файлы','Аналитика'],
    does:'Пишет посты, анализирует охваты, придумывает хуки для Reels, строит стратегию роста',
    example:'/аналитика → читает Instagram API → создаёт отчёт → рекомендует темы на неделю',
    trigger:'Каждый понедельник для контент-плана, по запросу для анализа' },
  { emoji:'✍️', name:'Виктория', role:'Редактор',         file:'victoria.py', color:G,
    knows:['Голос Людмилы','Пунктуация','Стиль'],
    does:'Проверяет каждый текст перед публикацией. Ничего не выходит без её одобрения',
    example:'Написала пост → Виктория проверяет → оценка 1-10 → правки → финальная версия',
    trigger:'Перед каждой публикацией' },
  { emoji:'👩', name:'Алина',    role:'Клиенты',          file:'alina.py',    color:'#2B7A8B',
    knows:['Анкеты','Методология','История сессий'],
    does:'Читает анкеты новых клиенток, определяет паттерн, готовит к сессии, делает сводки',
    example:'Новая анкета → Алина: паттерн Угодницы, 5 вопросов для сессии, красные флаги',
    trigger:'Перед каждой первой сессией' },
  { emoji:'💰', name:'Дима',     role:'Финансы',          file:'dima.py',     color:'#2C5F3A',
    knows:['Gumroad API','Продажи','Прогнозы'],
    does:'Считает доход, сравнивает с целями, строит прогнозы на квартал, находит узкие места',
    example:'/доход → Gumroad продажи + консультации = $3,840 CAD. Цель $5K — отставание 23%',
    trigger:'Каждое воскресенье и в конце месяца' },
  { emoji:'💬', name:'Тёма',     role:'Telegram',         file:'tyoma.py',    color:'#2B5278',
    knows:['Telegram Bot API','Цепочки','Контент'],
    does:'Публикует в канал, ведёт welcome-цепочку, отвечает на ХОЧУ, создаёт Telegram-контент',
    example:'/новые → 3 сообщения ХОЧУ → черновики ответов → Тёма ждёт подтверждения',
    trigger:'Ежедневно' },
  { emoji:'🔍', name:'Оля',      role:'Тренды',           file:'olya.py',     color:'#6B3FA0',
    knows:['Веб-поиск','Анализ','Конкуренты'],
    does:'Мониторит что вирусится прямо сейчас, анализирует конкурентов, находит свободные ниши',
    example:'/тренды → «тревожная привязанность после 40» — тема незанята, предлагает 5 хуков',
    trigger:'По запросу, перед съёмкой Reels' },
  { emoji:'📅', name:'Вася',     role:'Планировщик',      file:'vasya.py',    color:'#8B4513',
    knows:['Instagram API','Расписание','Контент'],
    does:'Планирует и ставит scheduled posts, ведёт расписание, напоминает что нужно снять',
    example:'/план → расписание на неделю: Пн 10:00 пост, Вт 18:00 Reel, Пт stories-оффер',
    trigger:'Каждый понедельник' },
  { emoji:'🎯', name:'Лера',     role:'Продажи',          file:'lera.py',     color:'#A84F3C',
    knows:['Воронка','Gumroad','Тексты'],
    does:'Пишет продающие тексты, оптимизирует воронку, придумывает акции, анализирует конверсию',
    example:'/оффер → 3 варианта продающего поста с разными триггерами и CTA',
    trigger:'Перед запуском акций, для продающих постов' },
];

const TOOLS = [
  { name:'read_file', desc:'Читает любой файл из E:\\MILA GOLD', who:'Все', icon:'📄',
    example:'read_file("content/posts/post_mon.txt") → текст поста' },
  { name:'write_file', desc:'Сохраняет результат в папку', who:'Все', icon:'💾',
    example:'write_file("analytics/report.md", "...") → создаёт файл' },
  { name:'list_files', desc:'Показывает содержимое папки', who:'Все', icon:'📁',
    example:'list_files("content") → список всех файлов' },
  { name:'instagram_get_analytics', desc:'Статистика аккаунта через Graph API', who:'Марина, Вася', icon:'📊',
    example:'→ 1340 подписчиков, охват 12K, топ-пост ID:123' },
  { name:'instagram_get_posts', desc:'Последние посты с метриками', who:'Марина, Лера', icon:'📱',
    example:'→ [пост: 234 лайка, 45 комментариев, сохранения 89]' },
  { name:'instagram_get_comments', desc:'Комментарии ко всем постам', who:'Марина', icon:'💬',
    example:'→ [{username: anna_23, text: "ХОЧУ", post_id: 123}]' },
  { name:'instagram_publish_post', desc:'Публикует фото с подписью', who:'Марина, Вася', icon:'📤',
    example:'→ ✓ Опубликовано! Post ID: 456789' },
  { name:'schedule_post', desc:'Ставит пост на определённое время', who:'Вася', icon:'⏰',
    example:'→ ✓ Запланировано на 2024-01-15T10:00Z' },
  { name:'telegram_send', desc:'Отправляет в Telegram-канал', who:'Тёма', icon:'✈️',
    example:'→ Черновик (ждёт подтверждения) / ✓ Опубликовано' },
  { name:'telegram_get_updates', desc:'Новые сообщения боту', who:'Тёма', icon:'📨',
    example:'→ [{from: Катя, text: "ХОЧУ", time: "14:23"}]' },
  { name:'gumroad_sales', desc:'Продажи практикума', who:'Дима, Лера', icon:'💰',
    example:'→ {count: 47, total_usd: 1739, sales: [...]}' },
  { name:'web_search', desc:'Поиск трендов и информации', who:'Оля', icon:'🔍',
    example:'→ топ результаты по запросу "тревожная привязанность"' },
  { name:'run_command', desc:'Запускает Python скрипты', who:'Марина', icon:'⚡',
    example:'→ python tools/get_analytics.py posts' },
];

const FOLDER = [
  { path:'E:\\MILA GOLD\\', type:'root', desc:'Корневая папка — все агенты работают здесь' },
  { path:'.env', type:'file', desc:'🔑 Все API ключи. НИКОМУ не показывай', important: true },
  { path:'content\\posts\\', type:'folder', desc:'Тексты постов (создаёт Марина, проверяет Виктория)' },
  { path:'content\\reels\\', type:'folder', desc:'Сценарии Reels (создаёт Марина, Оля)' },
  { path:'content\\stories\\', type:'folder', desc:'Stories и launch-контент' },
  { path:'content\\scheduled\\', type:'folder', desc:'Запланированные публикации (ведёт Вася)' },
  { path:'03-clients\\intake-forms\\', type:'folder', desc:'Анкеты новых клиенток (читает Алина)' },
  { path:'03-clients\\session-notes\\', type:'folder', desc:'Заметки после сессий (обрабатывает Алина)' },
  { path:'03-clients\\profiles\\', type:'folder', desc:'Профили клиенток с историей' },
  { path:'04-telegram\\', type:'folder', desc:'Контент для Telegram (ведёт Тёма)' },
  { path:'05-analytics\\', type:'folder', desc:'Отчёты, статистика, финансы (Марина, Дима)' },
  { path:'logs\\published.log', type:'file', desc:'История всех публикаций' },
  { path:'logs\\clients.log', type:'file', desc:'Лог работы с клиентками' },
];

const STARTUP_STEPS = [
  { step:1, title:'Установить Python 3.10+', detail:'python.org → скачать → установить', cmd:'python --version' },
  { step:2, title:'Распаковать mila-office.zip', detail:'В любую папку на компьютере', cmd:'' },
  { step:3, title:'Установить зависимости', detail:'Одна команда — устанавливает всё нужное', cmd:'pip install -r requirements.txt' },
  { step:4, title:'Создать .env файл', detail:'Скопировать env.template → E:\\MILA GOLD\\.env → вписать ключи', cmd:'' },
  { step:5, title:'Запустить офис', detail:'Открывается меню выбора агента', cmd:'python office.py' },
  { step:6, title:'Выбрать агента', detail:'Введи номер 1-8 и нажми Enter', cmd:'> 1  (Марина)' },
];

// ─── COMPONENTS ──────────────────────────────────────────

function Tag({ text, color = T }) {
  return <span style={{ fontSize:10, background:`${color}20`, color, padding:'2px 8px', borderRadius:8, border:`1px solid ${color}40`, whiteSpace:'nowrap' }}>{text}</span>;
}

function Card({ children, style = {} }) {
  return <div style={{ background:W, border:`1px solid ${B}`, borderRadius:14, padding:'20px', ...style }}>{children}</div>;
}

function OverviewSection() {
  return (
    <div>
      {/* Main diagram */}
      <Card style={{ marginBottom:16, background:N }}>
        <div style={{ fontSize:10, color:T, letterSpacing:2, marginBottom:16 }}>АРХИТЕКТУРА СИСТЕМЫ</div>
        <div style={{ display:'flex', gap:12, alignItems:'center', justifyContent:'center', flexWrap:'wrap' }}>
          {/* You */}
          <div style={{ textAlign:'center' }}>
            <div style={{ width:56, height:56, borderRadius:'50%', background:'rgba(196,97,74,0.2)', border:`2px solid ${T}`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, margin:'0 auto 8px' }}>👩</div>
            <div style={{ fontSize:12, color:W, fontWeight:600 }}>Ты</div>
            <div style={{ fontSize:10, color:'#9a7a6e' }}>пишешь задачу</div>
          </div>
          <div style={{ fontSize:24, color:T }}>→</div>
          {/* Office launcher */}
          <div style={{ textAlign:'center' }}>
            <div style={{ background:'rgba(196,97,74,0.15)', border:`1px solid ${T}`, borderRadius:10, padding:'10px 16px', marginBottom:8 }}>
              <div style={{ fontSize:20 }}>🏛</div>
              <div style={{ fontSize:11, color:W, fontWeight:600 }}>office.py</div>
            </div>
            <div style={{ fontSize:10, color:'#9a7a6e' }}>выбор агента</div>
          </div>
          <div style={{ fontSize:24, color:T }}>→</div>
          {/* Agents */}
          <div style={{ textAlign:'center' }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4, marginBottom:8 }}>
              {['📣','✍️','👩','💰','💬','🔍','📅','🎯'].map((e,i) => (
                <div key={i} style={{ background:'rgba(255,255,255,0.08)', borderRadius:6, padding:'4px 6px', fontSize:14 }}>{e}</div>
              ))}
            </div>
            <div style={{ fontSize:10, color:'#9a7a6e' }}>8 агентов</div>
          </div>
          <div style={{ fontSize:24, color:T }}>→</div>
          {/* Tools */}
          <div style={{ textAlign:'center' }}>
            <div style={{ background:'rgba(255,255,255,0.08)', borderRadius:10, padding:'10px 14px', marginBottom:8 }}>
              <div style={{ fontSize:10, color:'#9a7a6e', marginBottom:4 }}>инструменты</div>
              {['📱 Instagram','💬 Telegram','💰 Gumroad','📁 Файлы'].map((t,i) => (
                <div key={i} style={{ fontSize:10, color:W, padding:'1px 0' }}>{t}</div>
              ))}
            </div>
          </div>
          <div style={{ fontSize:24, color:T }}>→</div>
          {/* Result */}
          <div style={{ textAlign:'center' }}>
            <div style={{ background:'rgba(74,122,94,0.2)', border:'1px solid #4a7a5e', borderRadius:10, padding:'10px 14px', marginBottom:8 }}>
              <div style={{ fontSize:10, color:'#84c49a', marginBottom:4 }}>результат</div>
              {['Пост готов','Пост опубликован','Отчёт создан','Ответы написаны'].map((t,i) => (
                <div key={i} style={{ fontSize:10, color:W, padding:'1px 0' }}>✓ {t}</div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Key concepts */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))', gap:12 }}>
        {[
          { icon:'🧠', title:'Агент = Claude + роль + инструменты',
            desc:'Каждый агент — это Claude с конкретным системным промптом и набором инструментов. Марина знает маркетинг, Алина — клиентов, Дима — финансы.' },
          { icon:'🔄', title:'Агентный цикл',
            desc:'Ты пишешь задачу → агент думает → вызывает инструменты → получает данные → думает ещё → даёт ответ. Это повторяется пока задача не выполнена.' },
          { icon:'📁', title:'Общая память — папка',
            desc:'Все агенты читают и пишут в E:\\MILA GOLD. Марина создала пост → Виктория его читает → Вася публикует. Информация передаётся через файлы.' },
          { icon:'🔑', title:'API = руки агентов',
            desc:'Без API агенты могут только говорить. С API — публикуют посты, читают статистику, отправляют сообщения, проверяют продажи.' },
        ].map((c,i) => (
          <Card key={i}>
            <div style={{ fontSize:24, marginBottom:10 }}>{c.icon}</div>
            <div style={{ fontSize:13, fontWeight:600, color:N, marginBottom:6 }}>{c.title}</div>
            <div style={{ fontSize:12, color:U, lineHeight:1.6 }}>{c.desc}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function FlowSection() {
  const [step, setStep] = useState(0);
  const steps = [
    { title:'Ты пишешь задачу', icon:'💬',
      detail:'Например: "/аналитика" или "напиши пост о синдроме хорошей девочки"',
      code:'> /аналитика',
      result:'Марина получила запрос' },
    { title:'Claude читает задачу', icon:'🧠',
      detail:'Claude понимает что нужно сделать и решает какие инструменты использовать',
      code:`[думает]
Нужно:
1. Получить статистику Instagram
2. Проанализировать посты
3. Дать рекомендации`,
      result:'Составлен план действий' },
    { title:'Агент вызывает инструменты', icon:'🔧',
      detail:'Агент делает API вызовы, читает файлы, запускает скрипты',
      code:`🔧 instagram_get_analytics(period="week")
→ {reach: 12400, followers: 1340...}

🔧 instagram_get_posts(limit=10)
→ [{caption: "...", likes: 234, saves: 89}]`,
      result:'Данные получены' },
    { title:'Анализ и ответ', icon:'📊',
      detail:'Claude анализирует полученные данные и формирует ответ',
      code:`**Аналитика за неделю:**
- Охват: 12,400 (+18%)
- Лучший пост: про паттерн Спасателя
- Рекомендация: больше личных историй`,
      result:'Готово!' },
    { title:'Сохранение результата', icon:'💾',
      detail:'Если нужно — агент сохраняет результат в папку',
      code:`🔧 write_file("analytics/week_23.md", "...")
→ ✓ Сохранено: E:\\MILA GOLD\\analytics\\week_23.md`,
      result:'Файл создан' },
  ];
  const s = steps[step];
  return (
    <div>
      {/* Step nav */}
      <div style={{ display:'flex', gap:6, marginBottom:16, flexWrap:'wrap' }}>
        {steps.map((s,i) => (
          <button key={i} onClick={() => setStep(i)} style={{
            background: step===i ? T : M, color: step===i ? W : N,
            border: 'none', borderRadius:8, padding:'8px 14px', fontSize:12, cursor:'pointer'
          }}>{i+1}. {s.title}</button>
        ))}
      </div>

      {/* Step detail */}
      <Card style={{ borderColor: T, borderWidth:2 }}>
        <div style={{ display:'flex', gap:16, alignItems:'flex-start', marginBottom:16 }}>
          <div style={{ width:52, height:52, borderRadius:'50%', background:T, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, flexShrink:0 }}>{s.icon}</div>
          <div>
            <div style={{ fontSize:10, color:T, letterSpacing:2, marginBottom:4 }}>ШАГ {step+1} ИЗ {steps.length}</div>
            <div style={{ fontSize:20, fontWeight:600, color:N }}>{s.title}</div>
            <div style={{ fontSize:13, color:U, marginTop:4, lineHeight:1.5 }}>{s.detail}</div>
          </div>
        </div>

        <div style={{ background:N, borderRadius:10, padding:'16px', marginBottom:12, fontFamily:'monospace' }}>
          <div style={{ fontSize:10, color:T, letterSpacing:2, marginBottom:8 }}>КОНСОЛЬ</div>
          <pre style={{ fontSize:12, color:'#c0a898', lineHeight:1.8, margin:0, whiteSpace:'pre-wrap' }}>{s.code}</pre>
        </div>

        <div style={{ background:'rgba(74,122,94,0.1)', border:'1px solid #4a7a5e', borderRadius:8, padding:'10px 14px' }}>
          <span style={{ fontSize:11, color:'#4a7a5e', fontWeight:600 }}>✓ Результат: </span>
          <span style={{ fontSize:11, color:N }}>{s.result}</span>
        </div>
      </Card>

      <div style={{ display:'flex', justifyContent:'center', gap:8, marginTop:12 }}>
        <button onClick={() => setStep(Math.max(0,step-1))} disabled={step===0}
          style={{ background:step===0?B:T, color:W, border:'none', borderRadius:8, padding:'8px 20px', cursor:step===0?'default':'pointer' }}>← Назад</button>
        <button onClick={() => setStep(Math.min(steps.length-1,step+1))} disabled={step===steps.length-1}
          style={{ background:step===steps.length-1?B:T, color:W, border:'none', borderRadius:8, padding:'8px 20px', cursor:step===steps.length-1?'default':'pointer' }}>Вперёд →</button>
      </div>
    </div>
  );
}

function AgentsSection() {
  const [sel, setSel] = useState(0);
  const a = AGENTS[sel];
  return (
    <div>
      {/* Grid */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(110px, 1fr))', gap:8, marginBottom:16 }}>
        {AGENTS.map((ag,i) => (
          <button key={i} onClick={() => setSel(i)} style={{
            background: sel===i ? ag.color : W,
            border: `2px solid ${sel===i ? ag.color : B}`,
            borderRadius:12, padding:'14px 8px', cursor:'pointer', textAlign:'center'
          }}>
            <div style={{ fontSize:24, marginBottom:4 }}>{ag.emoji}</div>
            <div style={{ fontSize:12, fontWeight:600, color: sel===i ? W : N }}>{ag.name}</div>
            <div style={{ fontSize:10, color: sel===i ? 'rgba(255,255,255,0.7)' : U }}>{ag.role}</div>
          </button>
        ))}
      </div>

      {/* Detail */}
      <Card style={{ borderColor: a.color, borderWidth:2 }}>
        <div style={{ display:'flex', gap:14, alignItems:'center', marginBottom:16 }}>
          <div style={{ width:52, height:52, borderRadius:'50%', background:a.color, display:'flex', alignItems:'center', justifyContent:'center', fontSize:26, flexShrink:0 }}>{a.emoji}</div>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:20, fontWeight:600, color:N }}>{a.name}</div>
            <div style={{ fontSize:11, color:a.color, letterSpacing:1 }}>{a.role} · {a.file}</div>
          </div>
        </div>
        <div style={{ fontSize:13, color:N, lineHeight:1.6, marginBottom:16 }}>{a.does}</div>

        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:12 }}>
          <div>
            <div style={{ fontSize:10, color:a.color, letterSpacing:2, marginBottom:8 }}>ИНСТРУМЕНТЫ</div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {a.knows.map(k => <Tag key={k} text={k} color={a.color} />)}
            </div>
          </div>
          <div>
            <div style={{ fontSize:10, color:a.color, letterSpacing:2, marginBottom:8 }}>КОГДА ИСПОЛЬЗОВАТЬ</div>
            <div style={{ fontSize:12, color:U, lineHeight:1.5 }}>{a.trigger}</div>
          </div>
        </div>

        <div style={{ background:N, borderRadius:10, padding:'14px', fontFamily:'monospace' }}>
          <div style={{ fontSize:10, color:a.color, letterSpacing:2, marginBottom:8 }}>ПРИМЕР РАБОТЫ</div>
          <div style={{ fontSize:12, color:'#c0a898', lineHeight:1.8 }}>{a.example}</div>
        </div>
      </Card>
    </div>
  );
}

function ToolsSection() {
  const [sel, setSel] = useState(null);
  return (
    <div>
      <div style={{ fontSize:13, color:U, marginBottom:16, lineHeight:1.6 }}>
        Инструменты — это «руки» агентов. Без них агент может только говорить. С ними — читает файлы, вызывает API, публикует посты.
      </div>
      <div style={{ display:'grid', gap:8 }}>
        {TOOLS.map((t,i) => (
          <div key={i} onClick={() => setSel(sel===i?null:i)} style={{
            background: sel===i ? N : W, border:`1px solid ${sel===i ? T : B}`,
            borderRadius:12, padding:'14px 16px', cursor:'pointer', transition:'all 0.15s'
          }}>
            <div style={{ display:'flex', gap:12, alignItems:'center' }}>
              <span style={{ fontSize:20 }}>{t.icon}</span>
              <div style={{ flex:1 }}>
                <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:4 }}>
                  <code style={{ fontSize:12, background: sel===i ? 'rgba(255,255,255,0.1)' : M, color: sel===i ? T : N, padding:'2px 8px', borderRadius:6 }}>{t.name}</code>
                  <Tag text={`использует: ${t.who}`} color={sel===i ? '#c0a898' : U} />
                </div>
                <div style={{ fontSize:12, color: sel===i ? '#c0a898' : U }}>{t.desc}</div>
              </div>
              <div style={{ fontSize:16, color:T }}>{sel===i ? '−' : '+'}</div>
            </div>
            {sel===i && (
              <div style={{ marginTop:12, background:'rgba(255,255,255,0.05)', borderRadius:8, padding:'12px', fontFamily:'monospace' }}>
                <div style={{ fontSize:10, color:T, letterSpacing:2, marginBottom:6 }}>ПРИМЕР</div>
                <div style={{ fontSize:12, color:'#84c49a', lineHeight:1.7 }}>{t.example}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function FolderSection() {
  return (
    <div>
      <div style={{ fontSize:13, color:U, marginBottom:16, lineHeight:1.6 }}>
        Папка <code style={{ background:M, padding:'2px 6px', borderRadius:4 }}>E:\MILA GOLD</code> — общая память всех агентов. Один агент создаёт файл, другой читает. Так они «общаются».
      </div>
      <Card style={{ marginBottom:12 }}>
        <div style={{ fontFamily:'monospace' }}>
          {FOLDER.map((item,i) => {
            const indent = item.path.split('\\').length - (item.type==='root' ? 0 : 1);
            const isFile = item.type === 'file';
            return (
              <div key={i} style={{ display:'flex', gap:12, alignItems:'flex-start', padding:'8px 0', borderBottom: i<FOLDER.length-1 ? `1px solid ${B}` : 'none' }}>
                <div style={{ paddingLeft: indent*16, flexShrink:0 }}>
                  <span style={{ fontSize:14 }}>{item.type==='root' ? '🗂' : isFile ? '📄' : '📁'}</span>
                  {' '}
                  <code style={{ fontSize:12, color: item.important ? T : item.type==='root' ? N : '#5a3a2e', fontWeight: item.type==='root' ? 700 : 400 }}>
                    {item.path.split('\\').pop() || item.path}
                  </code>
                </div>
                <div style={{ fontSize:11, color:U, lineHeight:1.5 }}>{item.desc}</div>
              </div>
            );
          })}
        </div>
      </Card>
      <div style={{ background:'rgba(196,97,74,0.08)', border:`1px solid ${T}`, borderRadius:10, padding:'14px 16px' }}>
        <div style={{ fontSize:11, fontWeight:600, color:T, marginBottom:6 }}>⚠️ Про .env файл</div>
        <div style={{ fontSize:12, color:U, lineHeight:1.6 }}>
          Файл <code>.env</code> содержит все API ключи. Никогда не отправляй его в email, не показывай в скриншотах, не выкладывай в облако. Он должен быть только на твоём компьютере в папке MILA GOLD.
        </div>
      </div>
    </div>
  );
}

function StartupSection() {
  const [done, setDone] = useState([]);
  const toggle = (i) => setDone(d => d.includes(i) ? d.filter(x=>x!==i) : [...d,i]);
  return (
    <div>
      <div style={{ fontSize:13, color:U, marginBottom:16 }}>
        Отмечай шаги по мере выполнения. Весь процесс занимает ~10 минут.
      </div>
      {STARTUP_STEPS.map((s,i) => (
        <div key={i} onClick={() => toggle(i)} style={{
          background: done.includes(i) ? 'rgba(74,122,94,0.08)' : W,
          border:`1px solid ${done.includes(i) ? '#4a7a5e' : B}`,
          borderRadius:12, padding:'16px 18px', marginBottom:8, cursor:'pointer', transition:'all 0.15s'
        }}>
          <div style={{ display:'flex', gap:14, alignItems:'flex-start' }}>
            <div style={{ width:32, height:32, borderRadius:'50%', background: done.includes(i) ? G : T, color:W, fontSize:14, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
              {done.includes(i) ? '✓' : s.step}
            </div>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:14, fontWeight:600, color:N, marginBottom:4, textDecoration: done.includes(i) ? 'line-through' : 'none', opacity: done.includes(i) ? 0.6 : 1 }}>{s.title}</div>
              <div style={{ fontSize:12, color:U, marginBottom: s.cmd ? 8 : 0 }}>{s.detail}</div>
              {s.cmd && (
                <code style={{ display:'block', background:N, color:'#84c49a', padding:'8px 12px', borderRadius:8, fontSize:12, fontFamily:'monospace' }}>
                  {s.cmd}
                </code>
              )}
            </div>
          </div>
        </div>
      ))}
      {done.length === STARTUP_STEPS.length && (
        <div style={{ background:'rgba(74,122,94,0.15)', border:'2px solid #4a7a5e', borderRadius:12, padding:'20px', textAlign:'center', marginTop:12 }}>
          <div style={{ fontSize:32, marginBottom:8 }}>🎉</div>
          <div style={{ fontSize:16, fontWeight:600, color:N }}>Офис готов к работе!</div>
          <div style={{ fontSize:13, color:U, marginTop:4 }}>Все 8 агентов ждут твоих задач</div>
        </div>
      )}
    </div>
  );
}

// ─── MAIN ────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('overview');

  const renderTab = () => {
    if (tab === 'overview') return <OverviewSection />;
    if (tab === 'flow')     return <FlowSection />;
    if (tab === 'agents')   return <AgentsSection />;
    if (tab === 'tools')    return <ToolsSection />;
    if (tab === 'folder')   return <FolderSection />;
    if (tab === 'startup')  return <StartupSection />;
  };

  return (
    <div style={{ fontFamily:'Georgia, serif', background:C, minHeight:'100vh' }}>
      {/* Header */}
      <div style={{ background:N, padding:'24px 20px 28px' }}>
        <div style={{ maxWidth:820, margin:'0 auto' }}>
          <div style={{ fontSize:10, color:T, letterSpacing:3, marginBottom:8 }}>КАК РАБОТАЕТ · MILA OFFICE</div>
          <div style={{ fontSize:26, color:W, lineHeight:1.2 }}>Детальное объяснение</div>
          <div style={{ fontSize:12, color:'#5a3a2e', marginTop:4 }}>8 агентов · E:\MILA GOLD · Instagram + Telegram + Gumroad</div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ background:W, borderBottom:`1px solid ${B}`, position:'sticky', top:0, zIndex:10 }}>
        <div style={{ maxWidth:820, margin:'0 auto', display:'flex', overflowX:'auto' }}>
          {SECTIONS.map(s => (
            <button key={s.id} onClick={() => setTab(s.id)} style={{
              background:'none', border:'none', borderBottom:`3px solid ${tab===s.id ? T : 'transparent'}`,
              padding:'14px 16px', fontSize:13, color: tab===s.id ? T : U, cursor:'pointer',
              whiteSpace:'nowrap', fontFamily:'Georgia, serif', fontWeight: tab===s.id ? 600 : 400,
              transition:'all 0.15s'
            }}>{s.label}</button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth:820, margin:'0 auto', padding:'24px 20px 60px' }}>
        {renderTab()}
      </div>
    </div>
  );
}
