#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// A deliberately small JSON protocol: exactly "id" and "command", in either
// order. No duplicate keys, extra fields, escapes, or trailing data are allowed.
// Commands use ASCII letters, digits, or '_'; Chinese stays on the computer.
struct LedRequest {
    uint32_t id;
    char command[32];
};

namespace LedProtocol {
inline void skipSpace(const char *&p, const char *end) {
    while (p < end && (*p == ' ' || *p == '\t' || *p == '\r')) ++p;
}

inline bool take(const char *&p, const char *end, char expected) {
    skipSpace(p, end);
    if (p == end || *p != expected) return false;
    ++p;
    return true;
}

inline bool readString(const char *&p, const char *end, char *out, size_t capacity) {
    if (!take(p, end, '"')) return false;
    size_t n = 0;
    while (p < end && *p != '"') {
        const char c = *p++;
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= '0' && c <= '9') || c == '_') || n + 1 >= capacity) return false;
        out[n++] = c;
    }
    if (p == end || n == 0) return false;
    ++p;
    out[n] = '\0';
    return true;
}

inline bool readId(const char *&p, const char *end, uint32_t &id) {
    skipSpace(p, end);
    if (p == end || *p < '1' || *p > '9') return false;
    id = 0;
    while (p < end && *p >= '0' && *p <= '9') {
        const uint32_t digit = static_cast<uint32_t>(*p++ - '0');
        if (id > (2147483647UL - digit) / 10UL) return false;
        id = id * 10UL + digit;
    }
    return true;
}

inline bool parse(const char *data, size_t length, LedRequest &result) {
    const char *p = data;
    const char *end = data + length;
    LedRequest parsed = {};
    bool hasId = false, hasCommand = false;
    if (!take(p, end, '{')) return false;
    for (unsigned int field = 0; field < 2; ++field) {
        char key[16];
        if (!readString(p, end, key, sizeof(key)) || !take(p, end, ':')) return false;
        if (strcmp(key, "id") == 0 && !hasId) {
            if (!readId(p, end, parsed.id)) return false;
            hasId = true;
        } else if (strcmp(key, "command") == 0 && !hasCommand) {
            if (!readString(p, end, parsed.command, sizeof(parsed.command))) return false;
            hasCommand = true;
        } else {
            return false;
        }
        if (field == 0 && !take(p, end, ',')) return false;
    }
    if (!hasId || !hasCommand || !take(p, end, '}')) return false;
    skipSpace(p, end);
    if (p != end) return false;
    result = parsed;
    return true;
}
}  // namespace LedProtocol
