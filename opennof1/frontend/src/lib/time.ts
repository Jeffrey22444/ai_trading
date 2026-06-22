const BEIJING_TIME_ZONE = 'Asia/Shanghai';
const EXPLICIT_TIME_ZONE_RE = /(?:z|[+-]\d{2}:?\d{2})$/i;

function parseBackendTimestamp(timestamp: string): Date {
  const trimmed = timestamp.trim();
  if (EXPLICIT_TIME_ZONE_RE.test(trimmed)) {
    return new Date(trimmed);
  }

  const isoLike = trimmed.replace(' ', 'T');
  return new Date(`${isoLike}Z`);
}

export function formatBeijingCycleTimestamp(timestamp: string): string {
  const date = parseBackendTimestamp(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BEIJING_TIME_ZONE,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const valueByType = Object.fromEntries(
    parts.map((part) => [part.type, part.value])
  );

  return `${valueByType.month}/${valueByType.day} ${valueByType.hour}:${valueByType.minute} BJT`;
}
