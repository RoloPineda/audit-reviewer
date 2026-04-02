import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../context/AuthContext';

function wrapper({ children }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe('AuthContext', () => {
  it('starts unauthenticated', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.username).toBeUndefined();
  });

  it('stores credentials after login', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.login('admin', 'secret');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.username).toBe('admin');
  });

  it('generates correct Basic auth header', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.login('admin', 'secret');
    });

    const header = result.current.getAuthHeader();
    const expected = btoa('admin:secret');
    expect(header).toEqual({ Authorization: `Basic ${expected}` });
  });

  it('clears credentials on logout', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.login('admin', 'secret');
    });
    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.getAuthHeader()).toEqual({});
  });
});