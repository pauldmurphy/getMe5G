import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  computeSpatialKey,
  LruMemoryCache,
  AvailabilityCacheService,
} from '@/lib/db/cache';

describe('Multi-Tier Cache Layer Unit Tests (L1 LRU & L2 SQLite)', () => {
  describe('Spatial Coordinate Hashing & Precision (Tier 1 & 2)', () => {
    it('should compute spatial cache key with 4 decimal places of precision', () => {
      const key = computeSpatialKey(40.74844, -73.98573);
      expect(key).toBe('40.7484:-73.9857');
    });

    it('should map nearby coordinates within ~11 meters to identical cache key', () => {
      const key1 = computeSpatialKey(40.74841, -73.98572);
      const key2 = computeSpatialKey(40.74844, -73.98574);
      expect(key1).toBe(key2);
    });

    it('should map coordinates beyond ~11 meters to different cache keys', () => {
      const key1 = computeSpatialKey(40.7484, -73.9857);
      const key2 = computeSpatialKey(40.7501, -73.9857);
      expect(key1).not.toBe(key2);
    });
  });

  describe('L1 In-Memory LRU Cache (Tier 1 & 2)', () => {
    let l1Cache: LruMemoryCache<any>;

    beforeEach(() => {
      l1Cache = new LruMemoryCache<any>({ maxItems: 3, ttlMs: 1000 });
    });

    it('should set and retrieve item from memory', () => {
      l1Cache.set('key1', { brand: 't-mobile' });
      const item = l1Cache.get('key1');
      expect(item).toEqual({ brand: 't-mobile' });
    });

    it('should return null for non-existent key', () => {
      expect(l1Cache.get('missing-key')).toBeNull();
    });

    it('should evict least recently used item when max capacity is reached', () => {
      l1Cache.set('a', 1);
      l1Cache.set('b', 2);
      l1Cache.set('c', 3);

      // Access 'a' to make 'b' the least recently used
      l1Cache.get('a');

      // Insert 'd' (exceeding maxItems of 3)
      l1Cache.set('d', 4);

      expect(l1Cache.get('a')).toBe(1);
      expect(l1Cache.get('c')).toBe(3);
      expect(l1Cache.get('d')).toBe(4);
      expect(l1Cache.get('b')).toBeNull(); // 'b' was evicted
    });

    it('should respect TTL and expire items after timeout', async () => {
      vi.useFakeTimers();
      l1Cache.set('expiring-key', 'data', 500);

      expect(l1Cache.get('expiring-key')).toBe('data');

      // Fast forward past TTL
      vi.advanceTimersByTime(501);

      expect(l1Cache.get('expiring-key')).toBeNull();
      vi.useRealTimers();
    });
  });

  describe('Two-Tier Cache Orchestration (L1 Memory + L2 SQLite)', () => {
    let cacheService: AvailabilityCacheService;

    beforeEach(() => {
      cacheService = new AvailabilityCacheService();
      cacheService.clearAll();
    });

    it('should report cache miss on initial un-cached coordinate lookup', async () => {
      const result = await cacheService.get(40.7484, -73.9857);
      expect(result.hit).toBe(false);
      expect(result.layer).toBe('none');
      expect(result.data).toBeNull();
    });

    it('should store in cache and return L1 memory hit on immediate repeat query', async () => {
      const mockData = { providers: [{ brandId: 't-mobile-5g-home' }] };
      await cacheService.set(40.7484, -73.9857, mockData);

      const cached = await cacheService.get(40.7484, -73.9857);
      expect(cached.hit).toBe(true);
      expect(cached.layer).toBe('l1_memory');
      expect(cached.data).toEqual(mockData);
    });

    it('should fall back to L2 SQLite and backfill L1 if L1 is flushed', async () => {
      const mockData = { providers: [{ brandId: 'verizon-5g-home' }] };
      await cacheService.set(40.7484, -73.9857, mockData);

      // Flush only L1 memory
      cacheService.flushL1();

      // First query should hit L2 SQLite
      const l2Result = await cacheService.get(40.7484, -73.9857);
      expect(l2Result.hit).toBe(true);
      expect(l2Result.layer).toBe('l2_db');
      expect(l2Result.data).toEqual(mockData);

      // Subsequent query should now hit L1 because it was backfilled
      const l1Result = await cacheService.get(40.7484, -73.9857);
      expect(l1Result.hit).toBe(true);
      expect(l1Result.layer).toBe('l1_memory');
      expect(l1Result.data).toEqual(mockData);
    });

    it('should handle bypass flag to skip cache when fresh query is demanded', async () => {
      const mockData = { providers: [{ brandId: 'att-internet-air' }] };
      await cacheService.set(40.7484, -73.9857, mockData);

      const bypassed = await cacheService.get(40.7484, -73.9857, { bypassCache: true });
      expect(bypassed.hit).toBe(false);
      expect(bypassed.layer).toBe('none');
    });
  });
});
