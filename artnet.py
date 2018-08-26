import socket
import time

RED   = (0xFF, 0x00, 0x00)
GREEN = (0x00, 0xFF, 0x00)
BLUE  = (0x00, 0x00, 0xFF)
WHITE = (0xFF, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00)

class CandyMachine(object):
    def __init__(self, width=9, height=6):
        self.width, self.height = width, height
        self.surface = [[(0, 0, 0)] * self.width for y in range(0, self.height)]

    def drawPoint(self, x, y, color):
        if x < self.width and y < self.height:
            self.surface[int(y)][int(x)] = color

    def getPoint(self, x, y):
        if x < self.width and y < self.height:
            return self.surface[int(y)][int(x)]

    def drawVLine(self, xo, yo, length, color):
        for y in range(0, int(length)):
            self.drawPoint(xo, y + yo, color)

    def drawHLine(self, xo, yo, length, color):
        for x in range(0, int(length)):
            self.drawPoint(xo + x, yo, color)

    def fill(self, color):
        for x in range(0, self.width):
            for y in range(0, self.height):
                self.surface[y][x] = color

    def __bytes__(self):
        data = [int(color) for row in self.surface for pixel in row for color in pixel]
        return bytes(data)

class Artnet(object):
    def __init__(self, ip='candymachine.tkkrlab', port=6454):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.initialized = self.hostExists(self.ip)
        if self.initialized:
            self.sock.connect((self.ip, self.port))

    def hostExists(self, host):
        try:
            socket.gethostbyname(host)
            return True
        except Exception as e:
            return False
    
    def transmit(self, data):
        if self.sock is None:
            return

        if not self.initialized:
            return

        message = []
        message.extend(bytearray("Art-Net", "ascii"))
        message.append(0x00)
        message.append(0x00)
        message.append(0x50)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.append(0x00)
        message.extend(data)

        self.sock.sendall(bytearray(message))

    def receive(self):
        pass

    def close(self):
        self.sock.close()


if __name__ == "__main__":
    width, height = 9, 5
    artnet = Artnet()
    candy = CandyMachine()
    print(bytes(candy))

    candy.fill((0xff, 0xff, 0xff))
    for x in range(0, candy.width):
        candy.drawPoint(x, x, (0x00, 0x00, 0x00))
    artnet.transmit(bytes(candy))

    time.sleep(1)
    
    candy.fill((0, 0, 0))
    artnet.transmit(bytes(candy))

    time.sleep(1)

    for x in range(0, candy.width, 2):
        candy.drawVLine(x, 1, candy.height - 2, RED)
        candy.drawVLine(x + 1, 1, candy.height - 2, GREEN)
    artnet.transmit(bytes(candy))

    time.sleep(1)

    candy.fill(BLACK)
    artnet.transmit(bytes(candy))

    for y in range(0, candy.height, 2):
        candy.drawHLine(1, y, candy.width - 2, RED)
        candy.drawHLine(1, y + 1, candy.width - 2, RED)
    artnet.transmit(bytes(candy))

    # testdata = [0xFF] * (width * height) * 3
    # artnet.transmit(testdata)
    # time.sleep(1)
    
    # testdata = [0x00] * (width * height) * 3
    # artnet.transmit(testdata)
    artnet.close()

