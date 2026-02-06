'use client';

import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'krxusd-favorites';

export interface FavoriteStock {
  code: string;
  name: string;
  addedAt: number;
}

function loadFavorites(): FavoriteStock[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveFavorites(favorites: FavoriteStock[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // quota exceeded — ignore
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteStock[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setFavorites(loadFavorites());
    setHydrated(true);
  }, []);

  const isFavorite = useCallback(
    (code: string) => favorites.some((f) => f.code === code),
    [favorites]
  );

  const toggleFavorite = useCallback((code: string, name: string) => {
    setFavorites((prev) => {
      const exists = prev.some((f) => f.code === code);
      const next = exists
        ? prev.filter((f) => f.code !== code)
        : [...prev, { code, name, addedAt: Date.now() }];
      saveFavorites(next);
      return next;
    });
  }, []);

  const removeFavorite = useCallback((code: string) => {
    setFavorites((prev) => {
      const next = prev.filter((f) => f.code !== code);
      saveFavorites(next);
      return next;
    });
  }, []);

  return { favorites, isFavorite, toggleFavorite, removeFavorite, hydrated };
}
