/**
 * Masks sensitive keys by showing only the first 2 and last 2 characters
 * with asterisks in between
 * @param key - The sensitive key to mask
 * @param showChars - Number of characters to show at start and end (default: 2)
 * @returns Masked key string or null if input is null/undefined
 */
export function maskSensitiveKey(key: string | null | undefined, showChars: number = 2): string | null {
  if (!key || typeof key !== 'string' || key.trim() === '') {
    return null;
  }

  const MIN_ASTERISKS = 6; // Minimum number of asterisks to show in the middle
  
  const trimmedKey = key.trim();
  
  // If key is too short, mask it completely
  if (trimmedKey.length <= showChars * 2) {
    return '*'.repeat(trimmedKey.length);
  }
  
  const start = trimmedKey.substring(0, showChars);
  const end = trimmedKey.substring(trimmedKey.length - showChars);
  const middleLength = Math.max(MIN_ASTERISKS, trimmedKey.length - (showChars * 2)); // Minimum 6 asterisks
  
  return `${start}${'*'.repeat(middleLength)}${end}`;
}
