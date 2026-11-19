import { useState } from 'react';
import type { FormEvent } from 'react';

interface Props {
  error: string | null;
  onSubmit: (password: string) => Promise<boolean>;
}

export function LoginScreen({ error, onSubmit }: Props) {
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    const ok = await onSubmit(password);
    setSubmitting(false);
    if (ok) setPassword('');
  };

  return (
    <div className="flex h-screen items-center justify-center bg-[#f9f9f9]">
      <form
        onSubmit={handleSubmit}
        className="w-[320px] rounded-lg bg-white p-8 shadow-sm border border-gray-200"
      >
        <h1 className="text-lg font-semibold text-gray-900 mb-1">LearningEngine</h1>
        <p className="text-sm text-gray-500 mb-6">Sign in to continue</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-gray-900"
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-gray-900 text-white text-sm py-2 disabled:opacity-50"
        >
          {submitting ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
