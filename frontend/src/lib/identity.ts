function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getDeviceId(): string {
  let id = localStorage.getItem("device_id");
  if (!id) {
    id = uuid();
    localStorage.setItem("device_id", id);
  }
  return id;
}

export function getPairId(): string | null {
  return localStorage.getItem("pair_id");
}

export function setPairId(pairId: string): void {
  localStorage.setItem("pair_id", pairId);
}

export function getPartnerForSession(sessionId: string): "A" | "B" | null {
  const val = localStorage.getItem(`partner_${sessionId}`);
  return val === "A" || val === "B" ? val : null;
}

export function setPartnerForSession(sessionId: string, partner: "A" | "B"): void {
  localStorage.setItem(`partner_${sessionId}`, partner);
}
