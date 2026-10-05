import { useCallback, useEffect, useState } from 'react';
import * as authApi from '../api/auth';

type Status = 'checking' | 'authenticated' | 'unauthenticated';

export function useAuth() {
  const [status, setStatus] = useState<Status>('checking');
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    authApi
      .checkSession()
      .then((ok) => setStatus(ok ? 'authenticated' : 'unauthenticated'))
      .catch(() => setStatus('unauthenticated'));
  }, []);

  const submitLogin = useCallback(async (password: string) => {
    setLoginError(null);
    const ok = await authApi.login(password);
    if (ok) {
      setStatus('authenticated');
    } else {
      setLoginError('Incorrect password');
    }
    return ok;
  }, []);

  const signOut = useCallback(async () => {
    await authApi.logout();
    setStatus('unauthenticated');
  }, []);

  return { status, loginError, submitLogin, signOut };
}
