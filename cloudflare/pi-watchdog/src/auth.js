// Bearer-token checks shared by the routes.

// Compare two strings in time that doesn't depend on where they differ.
export function safeEqual(a, b) {
    const enc = new TextEncoder();
    const x = enc.encode(String(a));
    const y = enc.encode(String(b));
    let diff = x.length ^ y.length;
    for (let i = 0; i < x.length; i++) {
        diff |= x[i] ^ (y[i % y.length] ?? 0);
    }
    return diff === 0;
}

export function authorised(request, secret) {
    if (!secret) {
        return false;
    }
    const header = request.headers.get("Authorization") || "";
    const match = header.match(/^Bearer (.+)$/);
    return Boolean(match) && safeEqual(match[1], secret);
}
