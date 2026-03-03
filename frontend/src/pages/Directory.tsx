import { useState, useEffect, useRef } from 'react';
import api from '../api/client';

interface Criterion {
  key: string;
  description: string;
}

interface Reference {
  type: 'call' | 'client';
  id: number;
  label: string;
  detail: string;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  references?: Reference[];
}

const FALLBACK_CRITERIA: Criterion[] = [
  { key: 'greeting', description: 'Приветствие' },
  { key: 'name_ask', description: 'Уточнение имени' },
  { key: 'confirmation', description: 'Подтверждение' },
  { key: 'need_identification', description: 'Выявление потребности' },
  { key: 'solution_offer', description: 'Предложение решения' },
  { key: 'deadline', description: 'Согласование сроков' },
  { key: 'closing', description: 'Завершение разговора' },
];

export default function Directory() {
  // --- Checklist state ---
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.get('/api/assistant/criteria/')
      .then((res) => setCriteria(res.data))
      .catch(() => setCriteria(FALLBACK_CRITERIA));
  }, []);

  const toggleCriterion = (key: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      // If all are now checked, reset
      if (criteria.length > 0 && next.size === criteria.length) {
        return new Set();
      }
      return next;
    });
  };

  // --- Chat state ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setSending(true);
    try {
      const res = await api.post('/api/assistant/query/', { query: text });
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.data.answer, references: res.data.references },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Ошибка: не удалось получить ответ от сервера.' },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') sendMessage();
  };

  return (
    <div className="p-6 h-full flex flex-col">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Справочник</h2>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Left: AI Chat */}
        <div className="flex-1 flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-base font-semibold text-gray-800">AI-ассистент</h3>
            <p className="text-xs text-gray-500 mt-0.5">Задайте вопрос — поиск по звонкам и клиентам</p>
          </div>

          {/* Message history */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <p className="text-sm text-gray-400 text-center mt-8">
                Начните диалог — введите запрос ниже.
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  <p>{msg.text}</p>
                  {msg.references && msg.references.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {msg.references.map((ref, j) => (
                        <li key={j} className="text-xs bg-white/20 rounded px-2 py-1">
                          <span className="font-medium capitalize">{ref.type} #{ref.id}</span>
                          {' — '}{ref.label}
                          {ref.detail && (
                            <span className="block text-gray-500 mt-0.5">{ref.detail}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t border-gray-200 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Введите запрос..."
              disabled={sending}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {sending ? '...' : 'Отправить'}
            </button>
          </div>
        </div>

        {/* Right: Checklist */}
        <div className="w-80 flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-base font-semibold text-gray-800">Критерии оценки</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {checked.size}/{criteria.length} выполнено
            </p>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
            {criteria.length === 0 && (
              <p className="text-sm text-gray-400 text-center mt-4">Загрузка...</p>
            )}
            {criteria.map((c) => {
              const isChecked = checked.has(c.key);
              return (
                <button
                  key={c.key}
                  onClick={() => toggleCriterion(c.key)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-md hover:bg-gray-50 transition-colors text-left"
                >
                  {/* Circle toggle */}
                  <span
                    className={`w-6 h-6 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                      isChecked
                        ? 'bg-indigo-600 border-indigo-600'
                        : 'border-gray-400 bg-white'
                    }`}
                  >
                    {isChecked && (
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </span>
                  <span className={`text-sm ${isChecked ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                    {c.description}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
