// AMB82-MINI: Wi-Fi TCP LED endpoint. Speech recognition and UI run on the PC.
// Board: realtek:AmebaPro2:Ameba_AMB82-MINI (SDK 4.0.9 or compatible).
#include <WiFi.h>
#include <errno.h>
#include <stdio.h>
extern "C" {
#include <lwip/sockets.h>
}
#include "protocol.h"
#include "wifi_config.h"

const uint16_t TCP_PORT = 8266;
const unsigned long WIFI_RETRY_MS = 10000;
const unsigned long SERVER_RETRY_MS = 5000;
const unsigned long HANDSHAKE_TIMEOUT_MS = 5000;
const unsigned long IDLE_TIMEOUT_MS = 120000;
const unsigned long FRAME_TIMEOUT_MS = 3000;
const size_t MAX_FRAME_BYTES = 256;

char wifiSsid[] = WIFI_SSID;
const char wifiPassword[] = WIFI_PASSWORD;
int serverSocket = -1;
int clientSocket = -1;
bool sessionReady = false;
// These reflect outputs this firmware wrote, not an optical LED measurement.
bool blueOn = false;
bool greenOn = false;
bool wifiAttempted = false;
unsigned long lastWifiAttempt = 0;
unsigned long lastServerAttempt = 0;
unsigned long clientAcceptedAt = 0;
unsigned long lastRequestAt = 0;
unsigned long frameStartedAt = 0;
unsigned long lastIpPrint = 0;
char frame[MAX_FRAME_BYTES];
size_t frameLength = 0;

bool wouldBlock(int error) {
    return error == EAGAIN || error == EWOULDBLOCK || error == EINTR;
}

void closeClient() {
    if (clientSocket >= 0) lwip_close(clientSocket);
    clientSocket = -1;
    sessionReady = false;
    frameLength = 0;
}

void closeServer() {
    closeClient();
    if (serverSocket >= 0) lwip_close(serverSocket);
    serverSocket = -1;
}

bool setNonblocking(int socketFd) {
    const int flags = lwip_fcntl(socketFd, F_GETFL, 0);
    return flags >= 0 && lwip_fcntl(socketFd, F_SETFL, flags | O_NONBLOCK) == 0;
}

bool sendReply(uint32_t id, const char *command, bool ok, const char *error = NULL) {
    char reply[256];
    // All substituted text is either parser-restricted ASCII or a fixed literal.
    const int count = snprintf(reply, sizeof(reply),
        "{\"device\":\"AMB82-MINI\",\"protocol\":1,\"id\":%lu,\"command\":\"%s\","
        "\"ok\":%s,\"blue\":%s,\"green\":%s%s%s%s}\n",
        static_cast<unsigned long>(id), command, ok ? "true" : "false",
        blueOn ? "true" : "false", greenOn ? "true" : "false",
        error ? ",\"error\":\"" : "", error ? error : "", error ? "\"" : "");
    if (count <= 0 || static_cast<size_t>(count) >= sizeof(reply)) {
        closeClient();
        return false;
    }
    size_t written = 0;
    const unsigned long startedAt = millis();
    while (written < static_cast<size_t>(count) && millis() - startedAt < 1000) {
        const int sent = lwip_send(clientSocket, reply + written, count - written, 0);
        if (sent > 0) written += static_cast<size_t>(sent);
        else if (sent == 0 || !wouldBlock(errno)) break;
        else delay(1);
    }
    if (written != static_cast<size_t>(count)) {
        closeClient();
        return false;
    }
    return true;
}

void handleFrame() {
    LedRequest request = {};
    if (!LedProtocol::parse(frame, frameLength, request)) {
        sendReply(0, "", false, "MALFORMED_REQUEST");
        return;
    }
    lastRequestAt = millis();
    const char *command = request.command;
    if (strcmp(command, "HELLO") == 0) {
        sessionReady = true;
    } else if (!sessionReady) {
        sendReply(request.id, command, false, "HANDSHAKE_REQUIRED");
        return;
    } else if (strcmp(command, "BLUE_ON") == 0) {
        digitalWrite(LED_B, HIGH);
        blueOn = true;
    } else if (strcmp(command, "GREEN_ON") == 0) {
        digitalWrite(LED_G, HIGH);
        greenOn = true;
    } else if (strcmp(command, "ALL_OFF") == 0) {
        digitalWrite(LED_B, LOW);
        digitalWrite(LED_G, LOW);
        blueOn = false;
        greenOn = false;
    } else if (strcmp(command, "STATUS") != 0) {
        sendReply(request.id, command, false, "UNKNOWN_COMMAND");
        return;
    }
    sendReply(request.id, command, true);
}

void printAddress() {
    Serial.print("AMB_IP=");
    Serial.println(WiFi.localIP());
    Serial.print("TCP_PORT=");
    Serial.println(TCP_PORT);
    lastIpPrint = millis();
}

void startServer() {
    lastServerAttempt = millis();
    serverSocket = lwip_socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (serverSocket < 0) return;
    int reuse = 1;
    lwip_setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(TCP_PORT);
    address.sin_addr.s_addr = INADDR_ANY;
    if (!setNonblocking(serverSocket) ||
        lwip_bind(serverSocket, reinterpret_cast<struct sockaddr *>(&address), sizeof(address)) < 0 ||
        lwip_listen(serverSocket, 1) < 0) {
        closeServer();
        Serial.println("TCP server failed; retrying in 5 seconds.");
        return;
    }
    Serial.println("AMB82-MINI LED server ready.");
    printAddress();
}

bool maintainWifi() {
    if (WiFi.status() == WL_CONNECTED) {
        IPAddress ip = WiFi.localIP();
        if (ip[0] == 0) return false;  // Wait for DHCP before announcing readiness.
        if (serverSocket < 0 && (!lastServerAttempt || millis() - lastServerAttempt >= SERVER_RETRY_MS)) {
            startServer();
        }
        return serverSocket >= 0;
    }
    if (serverSocket >= 0) {
        Serial.println("Wi-Fi disconnected; reconnecting. LED outputs retained.");
        closeServer();
        lastServerAttempt = 0;
    }
    if (!wifiAttempted || millis() - lastWifiAttempt >= WIFI_RETRY_MS) {
        wifiAttempted = true;
        Serial.println("Connecting to configured Wi-Fi...");
        // WiFi.begin uses the SDK's bounded connection attempt. No endless
        // setup loop: after failure the main loop waits before the next attempt.
        WiFi.begin(wifiSsid, wifiPassword);
        lastWifiAttempt = millis();
        if (WiFi.status() != WL_CONNECTED) Serial.println("Wi-Fi failed; retrying in 10 seconds.");
    }
    return false;
}

void acceptClient() {
    // lwIP sockets are used directly: this SDK's WiFiClient convenience wrapper
    // does not preserve the error/partial-write details needed by this protocol.
    const int accepted = lwip_accept(serverSocket, NULL, NULL);
    if (accepted < 0) return;
    if (clientSocket >= 0 || !setNonblocking(accepted)) {
        lwip_close(accepted);  // This small application serves one desktop.
        return;
    }
    clientSocket = accepted;
    sessionReady = false;
    frameLength = 0;
    clientAcceptedAt = lastRequestAt = millis();
    Serial.println("Desktop connected; waiting for HELLO.");
}

void receiveClient() {
    if (clientSocket < 0) return;
    const unsigned long now = millis();
    if ((!sessionReady && now - clientAcceptedAt > HANDSHAKE_TIMEOUT_MS) ||
        now - lastRequestAt > IDLE_TIMEOUT_MS ||
        (frameLength > 0 && now - frameStartedAt > FRAME_TIMEOUT_MS)) {
        closeClient();
        return;
    }
    // Limit bytes per loop so network handling cannot starve Wi-Fi maintenance.
    uint8_t received[128];
    const int count = lwip_recv(clientSocket, received, sizeof(received), 0);
    if (count == 0 || (count < 0 && !wouldBlock(errno))) {
        closeClient();
        return;
    }
    for (int i = 0; i < count && clientSocket >= 0; ++i) {
        const char c = static_cast<char>(received[i]);
        if (c == '\n') {
            handleFrame();
            frameLength = 0;
        } else if (frameLength >= MAX_FRAME_BYTES) {
            sendReply(0, "", false, "FRAME_TOO_LONG");
            closeClient();  // Discard the entire oversized frame, including suffix.
        } else {
            if (frameLength == 0) frameStartedAt = millis();
            frame[frameLength++] = c;
        }
    }
}

void setup() {
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);  // D23 / PF9, active HIGH.
    pinMode(LED_G, OUTPUT);  // D24 / PE6, active HIGH.
    digitalWrite(LED_B, LOW);
    digitalWrite(LED_G, LOW);
    Serial.println("AMB82-MINI voice LED endpoint starting (protocol 1).");
}

void loop() {
    if (maintainWifi()) {
        receiveClient();
        acceptClient();
        if (millis() - lastIpPrint >= 30000) printAddress();
    }
    delay(5);
}
