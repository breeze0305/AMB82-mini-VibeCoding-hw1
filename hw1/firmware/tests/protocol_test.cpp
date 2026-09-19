#include "../amb82_voice_led/protocol.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned int checks = 0;

static void expect(bool value, const char *message) {
    ++checks;
    if (!value) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(1);
    }
}

int main() {
    LedRequest result = {};
    const char *valid[] = {
        "{\"id\":1,\"command\":\"HELLO\"}",
        " { \"command\" : \"BLUE_ON\", \"id\" : 2147483647 }\r",
        "{\"command\":\"GREEN_ON\",\"id\":42}",
        "{\"id\":2,\"command\":\"STATUS\"}",
        "{\"id\":3,\"command\":\"ALL_OFF\"}",
        "{\"id\":4,\"command\":\"UNKNOWN_COMMAND\"}"
    };
    for (const char *request : valid) {
        expect(LedProtocol::parse(request, strlen(request), result), request);
    }
    const char *invalid[] = {
        "", "{}", "[]", "null", "true",
        "{\"id\":0,\"command\":\"BLUE_ON\"}",
        "{\"id\":-1,\"command\":\"BLUE_ON\"}",
        "{\"id\":01,\"command\":\"BLUE_ON\"}",
        "{\"id\":1.0,\"command\":\"BLUE_ON\"}",
        "{\"id\":1e1,\"command\":\"BLUE_ON\"}",
        "{\"id\":true,\"command\":\"BLUE_ON\"}",
        "{\"id\":\"1\",\"command\":\"BLUE_ON\"}",
        "{\"id\":2147483648,\"command\":\"BLUE_ON\"}",
        "{\"id\":429496729600000000000000,\"command\":\"BLUE_ON\"}",
        "{\"id\":1,\"id\":2}",
        "{\"command\":\"HELLO\",\"command\":\"BLUE_ON\"}",
        "{\"id\":1,\"command\":\"BLUE_ON\",\"id\":2}",
        "{\"id\":1,\"command\":\"BLUE_ON\",\"extra\":0}",
        "{\"id\":1,\"command\":\"BLUE_ON\",}",
        "{\"id\":1,\"command\":\"BLUE_ON\"} trailing",
        "{\"id\":1,\"command\":\"BLUE_ON\"}{\"id\":2,\"command\":\"GREEN_ON\"}",
        "{\"id\":1,\"command\":null}",
        "{\"id\":1,\"command\":\"\"}",
        "{\"id\":1,\"command\":\"BLUE_ON\\u0000\"}",
        "{\"id\":1,\"command\":\"BLUE_ON\\\"\"}",
        "{\"id\":1,\"command\":\"BLUE_ON extra\"}",
        "{\"id\":1,\"command\":\"ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\"}",
        "{\"id\":1 \"command\":\"BLUE_ON\"}",
        "{\"id\":1,\"command\":\"BLUE_ON\"\n}"
    };
    for (const char *request : invalid) {
        result.id = 999;
        memcpy(result.command, "UNCHANGED", sizeof("UNCHANGED"));
        expect(!LedProtocol::parse(request, strlen(request), result), request);
        expect(result.id == 999 && strcmp(result.command, "UNCHANGED") == 0,
               "Rejected input must not modify the output request");
    }
    const char *request = valid[0];
    for (size_t n = 0; n < strlen(request); ++n) {
        expect(!LedProtocol::parse(request, n, result), "Truncated frame rejected");
    }
    const char embeddedNul[] = "{\"id\":1,\"command\":\"BLUE_ON\"}\0junk";
    expect(!LedProtocol::parse(embeddedNul, sizeof(embeddedNul) - 1, result),
           "Embedded NUL cannot hide trailing bytes");
    expect(LedProtocol::parse(valid[1], strlen(valid[1]), result), "Reordered fields accepted");
    expect(result.id == 2147483647UL && strcmp(result.command, "BLUE_ON") == 0,
           "ID and command preserved exactly");
    printf("PASS: %u protocol checks\n", checks);
    return 0;
}
