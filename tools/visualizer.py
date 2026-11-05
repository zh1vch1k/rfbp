#!/usr/bin/env python3
"""
RFBP v1.3.0 — Interactive Protocol Inspector & Live Telemetry HUD
Visualizes controller input normalization, bit-packing, Speck64/128 CTR encryption,
and the exact 8-byte over-the-air frame in real-time.
"""

import sys
import math
import time
import struct

try:
    import pygame
except ImportError:
    print("\n[ERROR] Pygame is required for the visualizer.")
    print("Please install it via: pip install pygame\n")
    sys.exit(1)

# ==============================================================================
# RFBP PROTOCOL ENGINE (C++ MATCHING LOGIC)
# ==============================================================================

SECRET_KEY = bytes([
    0x17, 0xFE, 0x05, 0x1D, 0xCC, 0xB5, 0x3A, 0xAE,
    0x2B, 0x7E, 0x15, 0x16, 0x28, 0xAE, 0xD2, 0xA6
])

def ror32(x, r):
    return ((x >> r) | (x << (32 - r))) & 0xFFFFFFFF

def rol32(x, r):
    return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF

def speck_round(x, y, k):
    x = ((ror32(x, 8) + y) & 0xFFFFFFFF) ^ k
    y = rol32(y, 3) ^ x
    return x, y

def speck_init(key_bytes):
    k = list(struct.unpack("<4I", key_bytes))
    round_keys = [0] * 27
    round_keys[0] = k[0]
    l = [k[1], k[2], k[3]]
    for i in range(26):
        target_idx = i % 3
        x = l[target_idx]
        y = round_keys[i]
        x, y = speck_round(x, y, i)
        l[target_idx] = x
        round_keys[i + 1] = y
    return round_keys

def speck_encrypt_block(round_keys, in_bytes):
    y, x = struct.unpack("<2I", in_bytes)
    for i in range(27):
        x, y = speck_round(x, y, round_keys[i])
    return struct.pack("<2I", y, x)

def speck_ctr_crypt(round_keys, session_id, cnt, data):
    nonce = ((session_id & 0xFFFFFFFF) << 32) | (cnt & 0xFFFFFFFF)
    nonce_bytes = struct.pack("<Q", nonce)
    keystream = speck_encrypt_block(round_keys, nonce_bytes)
    return bytes(d ^ k for d, k in zip(data, keystream[:len(data)]))

def crc8_calc(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

def scale_stick(val: float, deadzone: float = 0.30, invert: bool = False) -> int:
    if invert:
        val = -val
    if abs(val) <= deadzone:
        return 64
    val = max(-1.0, min(1.0, val))
    scaled = round((val + 1.0) * 0.5 * 127.0)
    return max(0, min(127, scaled))

def scale_trigger(val: float, starts_at_minus_one: bool = False) -> int:
    norm = (val + 1.0) * 0.5 if starts_at_minus_one else val
    norm = max(0.0, min(1.0, norm))
    scaled = round(norm * 15.0)
    return max(0, min(15, scaled))

def pack_payload(lx, ly, rx, ry, btn, tl, tr) -> bytes:
    u32 = (lx & 0x7F) | ((ly & 0x7F) << 7) | ((rx & 0x7F) << 14) | ((ry & 0x7F) << 21) | ((btn & 0x0F) << 28)
    b0_3 = struct.pack("<I", u32)
    b4 = struct.pack("B", (tl & 0x0F) | ((tr & 0x0F) << 4))
    return b0_3 + b4

# ==============================================================================
# UI & VISUALIZATION ENGINE
# ==============================================================================

WIDTH, HEIGHT = 1100, 700
FPS = 60

# Palette
BG_COLOR       = (13, 17, 23)
PANEL_BG       = (22, 27, 34)
PANEL_BORDER   = (48, 54, 61)
TEXT_WHITE     = (240, 246, 252)
TEXT_MUTED     = (139, 148, 158)
CYAN           = (0, 240, 255)
AMBER          = (255, 166, 87)
LIME           = (57, 255, 20)
MAGENTA        = (218, 54, 150)
PURPLE         = (188, 140, 255)
RED            = (248, 81, 73)
GRID_LINE      = (33, 38, 45)

class RFBPVisualizer:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("RFBP v1.3.0 — Interactive Protocol Inspector")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("menlo,consolas,monospace", 17, bold=True)
        self.font_mono  = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_bold  = pygame.font.SysFont("menlo,consolas,monospace", 13, bold=True)
        self.font_hex   = pygame.font.SysFont("menlo,consolas,monospace", 20, bold=True)
        self.font_sm    = pygame.font.SysFont("menlo,consolas,monospace", 10)

        # Gamepad setup
        pygame.joystick.init()
        self.joystick = None
        self.detect_gamepad()

        # Protocol State
        self.speck_keys = speck_init(SECRET_KEY)
        self.session_id = 0xABCD1234
        self.seq_num = 0
        self.mode = 2
        self.encryption_enabled = True
        self.demo_mode = False

        # Input states
        self.raw_lx, self.raw_ly = 0.0, 0.0
        self.raw_rx, self.raw_ry = 0.0, 0.0
        self.raw_lt, self.raw_rt = 0.0, 0.0
        self.buttons = 0  # 4-bit mask
        self.deadzone = 0.30
        self.active_drag = None

    def detect_gamepad(self):
        if pygame.joystick.get_count() > 0:
            try:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
            except pygame.error:
                self.joystick = None
        else:
            self.joystick = None

    def update_inputs(self, t):
        if self.demo_mode:
            self.raw_lx = math.cos(t * 1.5) * 0.85
            self.raw_ly = math.sin(t * 2.1) * 0.85
            self.raw_rx = math.sin(t * 1.2) * 0.90
            self.raw_ry = math.cos(t * 1.8) * 0.90
            self.raw_lt = (math.sin(t * 2.5) + 1.0) * 0.5
            self.raw_rt = (math.cos(t * 3.0) + 1.0) * 0.5
            if int(t * 2) % 4 == 0:
                self.buttons = 0b0101
            elif int(t * 2) % 4 == 2:
                self.buttons = 0b1010
            else:
                self.buttons = 0b0000
            return

        if self.joystick:
            try:
                name = self.joystick.get_name().lower()
                is_dualsense = "wireless controller" in name or "dualsense" in name or "ps5" in name
                is_xbox = "xbox" in name or "x-box" in name

                self.raw_lx = self.joystick.get_axis(0)
                self.raw_ly = self.joystick.get_axis(1)

                if is_xbox:
                    rx_idx, ry_idx = (3, 4) if self.joystick.get_numaxes() > 4 else (2, 3)
                    self.raw_rx = self.joystick.get_axis(rx_idx)
                    self.raw_ry = self.joystick.get_axis(ry_idx)
                    lt_axis = self.joystick.get_axis(2) if self.joystick.get_numaxes() > 4 else 0.0
                    rt_axis = self.joystick.get_axis(5) if self.joystick.get_numaxes() > 5 else 0.0
                    self.raw_lt = max(0.0, lt_axis)
                    self.raw_rt = max(0.0, rt_axis)
                else:
                    self.raw_rx = self.joystick.get_axis(2) if self.joystick.get_numaxes() > 2 else 0.0
                    self.raw_ry = self.joystick.get_axis(3) if self.joystick.get_numaxes() > 3 else 0.0
                    lt_axis = self.joystick.get_axis(4) if self.joystick.get_numaxes() > 4 else -1.0
                    rt_axis = self.joystick.get_axis(5) if self.joystick.get_numaxes() > 5 else -1.0
                    self.raw_lt = (lt_axis + 1.0) * 0.5 if is_dualsense else max(0.0, lt_axis)
                    self.raw_rt = (rt_axis + 1.0) * 0.5 if is_dualsense else max(0.0, rt_axis)

                # Buttons
                btn_mask = 0
                num_btns = self.joystick.get_numbuttons()
                if is_dualsense:
                    if num_btns > 7 and self.joystick.get_button(7): btn_mask |= (1 << 0)
                    if num_btns > 8 and self.joystick.get_button(8): btn_mask |= (1 << 1)
                    if num_btns > 9 and self.joystick.get_button(9): btn_mask |= (1 << 2)
                    if num_btns > 10 and self.joystick.get_button(10): btn_mask |= (1 << 3)
                elif is_xbox:
                    if num_btns > 8 and self.joystick.get_button(8): btn_mask |= (1 << 0)
                    if num_btns > 9 and self.joystick.get_button(9): btn_mask |= (1 << 1)
                    if num_btns > 4 and self.joystick.get_button(4): btn_mask |= (1 << 2)
                    if num_btns > 5 and self.joystick.get_button(5): btn_mask |= (1 << 3)
                else:
                    for i in range(min(4, num_btns)):
                        if self.joystick.get_button(i): btn_mask |= (1 << i)
                self.buttons = btn_mask
            except pygame.error:
                self.detect_gamepad()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                self.detect_gamepad()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.demo_mode = not self.demo_mode
                elif event.key == pygame.K_e:
                    self.encryption_enabled = not self.encryption_enabled
                elif event.key == pygame.K_r:
                    self.seq_num = 0
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7):
                    self.mode = event.key - pygame.K_0
                elif event.key == pygame.K_ESCAPE:
                    return False
            elif event.type == pygame.MOUSEBUTTONDOWN and not self.demo_mode:
                mx, my = event.pos
                if math.hypot(mx - 150, my - 210) <= 70:
                    self.active_drag = "left_stick"
                elif math.hypot(mx - 370, my - 210) <= 70:
                    self.active_drag = "right_stick"
                elif 50 <= mx <= 230 and 420 <= my <= 455:
                    self.buttons ^= (1 << 0)
                elif 250 <= mx <= 430 and 420 <= my <= 455:
                    self.buttons ^= (1 << 1)
                elif 50 <= mx <= 230 and 470 <= my <= 505:
                    self.buttons ^= (1 << 2)
                elif 250 <= mx <= 430 and 470 <= my <= 505:
                    self.buttons ^= (1 << 3)
                elif 510 <= mx <= 700 and 620 <= my <= 660:
                    self.encryption_enabled = not self.encryption_enabled
                elif 720 <= mx <= 900 and 620 <= my <= 660:
                    self.demo_mode = not self.demo_mode
            elif event.type == pygame.MOUSEBUTTONUP:
                if self.active_drag:
                    if self.active_drag == "left_stick":
                        self.raw_lx, self.raw_ly = 0.0, 0.0
                    elif self.active_drag == "right_stick":
                        self.raw_rx, self.raw_ry = 0.0, 0.0
                    self.active_drag = None
            elif event.type == pygame.MOUSEMOTION and self.active_drag and not self.demo_mode:
                mx, my = event.pos
                if self.active_drag == "left_stick":
                    self.raw_lx = max(-1.0, min(1.0, (mx - 150) / 70.0))
                    self.raw_ly = max(-1.0, min(1.0, (my - 210) / 70.0))
                elif self.active_drag == "right_stick":
                    self.raw_rx = max(-1.0, min(1.0, (mx - 370) / 70.0))
                    self.raw_ry = max(-1.0, min(1.0, (my - 210) / 70.0))
        return True

    def draw_panel(self, rect, title=""):
        pygame.draw.rect(self.screen, PANEL_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=1, border_radius=8)
        if title:
            surf = self.font_title.render(title, True, CYAN)
            self.screen.blit(surf, (rect[0] + 16, rect[1] + 14))

    def draw_stick_radar(self, cx, cy, radius, x_val, y_val, label, color):
        # Background & deadzone
        pygame.draw.circle(self.screen, (28, 35, 45), (cx, cy), radius)
        dz_r = int(radius * self.deadzone)
        pygame.draw.circle(self.screen, (38, 48, 62), (cx, cy), dz_r, width=1)
        pygame.draw.line(self.screen, GRID_LINE, (cx - radius, cy), (cx + radius, cy))
        pygame.draw.line(self.screen, GRID_LINE, (cx, cy - radius), (cx, cy + radius))
        pygame.draw.circle(self.screen, PANEL_BORDER, (cx, cy), radius, width=2)

        # Dot
        px = cx + int(x_val * radius)
        py = cy + int(y_val * radius)
        pygame.draw.line(self.screen, (*color, 120), (cx, cy), (px, py), width=2)
        pygame.draw.circle(self.screen, color, (px, py), 7)
        pygame.draw.circle(self.screen, TEXT_WHITE, (px, py), 3)

        # Text
        txt = self.font_bold.render(label, True, TEXT_WHITE)
        self.screen.blit(txt, (cx - txt.get_width() // 2, cy + radius + 10))

    def draw(self):
        self.screen.fill(BG_COLOR)

        # ----------------------------------------------------------------------
        # Top Header
        # ----------------------------------------------------------------------
        title = self.font_title.render("RFBP v1.3.0 — RADIO FAST BITMAP PROTOCOL INSPECTOR", True, TEXT_WHITE)
        self.screen.blit(title, (24, 18))
        
        status_txt = "DEMO SIMULATION" if self.demo_mode else (
            f"DEVICE: {self.joystick.get_name()}" if self.joystick else "MOUSE/KEYBOARD (CLICK STICKS)"
        )
        status_col = AMBER if self.demo_mode else (LIME if self.joystick else CYAN)
        status_surf = self.font_mono.render(status_txt, True, status_col)
        self.screen.blit(status_surf, (WIDTH - status_surf.get_width() - 24, 20))

        # ----------------------------------------------------------------------
        # PANEL 1: Controller Input & Scaling (Left)
        # ----------------------------------------------------------------------
        self.draw_panel((20, 55, 460, 480), "1. INPUT CONTROLLER & NORMALIZATION")

        # Radars
        self.draw_stick_radar(130, 180, 65, self.raw_lx, self.raw_ly, "LEFT STICK", CYAN)
        self.draw_stick_radar(330, 180, 65, self.raw_rx, self.raw_ry, "RIGHT STICK", AMBER)

        # Quantized values
        lx_7b = scale_stick(self.raw_lx, self.deadzone)
        ly_7b = scale_stick(self.raw_ly, self.deadzone)
        rx_7b = scale_stick(self.raw_rx, self.deadzone)
        ry_7b = scale_stick(self.raw_ry, self.deadzone)

        val_l = self.font_mono.render(f"LX: {self.raw_lx:+0.2f} -> 7b:{lx_7b:3d}", True, CYAN)
        val_ly = self.font_mono.render(f"LY: {self.raw_ly:+0.2f} -> 7b:{ly_7b:3d}", True, CYAN)
        val_r = self.font_mono.render(f"RX: {self.raw_rx:+0.2f} -> 7b:{rx_7b:3d}", True, AMBER)
        val_ry = self.font_mono.render(f"RY: {self.raw_ry:+0.2f} -> 7b:{ry_7b:3d}", True, AMBER)
        self.screen.blit(val_l, (60, 275))
        self.screen.blit(val_ly, (60, 295))
        self.screen.blit(val_r, (260, 275))
        self.screen.blit(val_ry, (260, 295))

        # Triggers
        tl_4b = scale_trigger(self.raw_lt)
        tr_4b = scale_trigger(self.raw_rt)

        self.screen.blit(self.font_bold.render("L-TRIGGER (4b)", True, TEXT_WHITE), (50, 330))
        pygame.draw.rect(self.screen, (33, 38, 45), (50, 350, 160, 14), border_radius=4)
        pygame.draw.rect(self.screen, LIME, (50, 350, int(160 * (tl_4b / 15.0)), 14), border_radius=4)
        self.screen.blit(self.font_mono.render(f"{tl_4b:2d}/15", True, TEXT_WHITE), (220, 348))

        self.screen.blit(self.font_bold.render("R-TRIGGER (4b)", True, TEXT_WHITE), (260, 330))
        pygame.draw.rect(self.screen, (33, 38, 45), (260, 350, 160, 14), border_radius=4)
        pygame.draw.rect(self.screen, LIME, (260, 350, int(160 * (tr_4b / 15.0)), 14), border_radius=4)
        self.screen.blit(self.font_mono.render(f"{tr_4b:2d}/15", True, TEXT_WHITE), (430, 348))

        # Buttons (4-bit mask)
        btn_labels = [("L-STICK CLICK (L3)", 0), ("R-STICK CLICK (R3)", 1), ("L1 / LB BUMPER", 2), ("R1 / RB BUMPER", 3)]
        coords = [(50, 395), (250, 395), (50, 445), (250, 445)]
        for (lbl, bit), (bx, by) in zip(btn_labels, coords):
            active = bool(self.buttons & (1 << bit))
            bg = LIME if active else (28, 35, 45)
            fg = (0, 0, 0) if active else TEXT_MUTED
            pygame.draw.rect(self.screen, bg, (bx, by, 180, 36), border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, (bx, by, 180, 36), width=1, border_radius=6)
            txt = self.font_mono.render(f"[x] {lbl}" if active else f"[ ] {lbl}", True, fg)
            self.screen.blit(txt, (bx + 12, by + 10))

        # ----------------------------------------------------------------------
        # Bit-Packing & Wire Encoding
        # ----------------------------------------------------------------------
        raw_payload = pack_payload(lx_7b, ly_7b, rx_7b, ry_7b, self.buttons, tl_4b, tr_4b)

        if self.encryption_enabled:
            tx_payload = speck_ctr_crypt(self.speck_keys, self.session_id, self.seq_num, raw_payload)
        else:
            tx_payload = raw_payload

        crc = crc8_calc(tx_payload)
        header_byte = (5 & 0x1F) | ((self.mode & 0x07) << 5)
        ota_frame = bytes([header_byte, self.seq_num & 0xFF]) + tx_payload + bytes([crc])

        # ----------------------------------------------------------------------
        # PANEL 2: Protocol Wire Frame (Right)
        # ----------------------------------------------------------------------
        self.draw_panel((500, 55, 580, 480), "2. OVER-THE-AIR LORA FRAME (EXACT 8 BYTES / 64 BITS)")

        desc = self.font_mono.render("Strictly sized to 8 bytes to match Speck64/128 cipher block size.", True, TEXT_MUTED)
        self.screen.blit(desc, (520, 95))

        # 8 Hex Badges
        labels = ["HDR/MODE", "SEQ_NUM", "PAYLOAD 0", "PAYLOAD 1", "PAYLOAD 2", "PAYLOAD 3", "PAYLOAD 4", "CRC8"]
        colors = [PURPLE, CYAN, AMBER, AMBER, AMBER, AMBER, AMBER, LIME]

        start_x, start_y = 520, 130
        badge_w, badge_h = 62, 70

        for i in range(8):
            bx = start_x + i * 69
            val = ota_frame[i]
            col = colors[i]

            pygame.draw.rect(self.screen, (28, 35, 45), (bx, start_y, badge_w, badge_h), border_radius=6)
            pygame.draw.rect(self.screen, col, (bx, start_y, badge_w, badge_h), width=2, border_radius=6)

            h_str = f"0x{val:02X}"
            h_surf = self.font_hex.render(h_str, True, TEXT_WHITE)
            self.screen.blit(h_surf, (bx + (badge_w - h_surf.get_width()) // 2, start_y + 12))

            idx_surf = self.font_sm.render(f"B{i}", True, col)
            self.screen.blit(idx_surf, (bx + (badge_w - idx_surf.get_width()) // 2, start_y + 38))

            lbl_surf = self.font_sm.render(labels[i], True, TEXT_MUTED)
            self.screen.blit(lbl_surf, (bx + (badge_w - lbl_surf.get_width()) // 2, start_y + 52))

        # Payload Bitstream Breakdown (40 bits)
        self.screen.blit(self.font_bold.render("40-BIT PACKED BITSTREAM BREAKDOWN:", True, TEXT_WHITE), (520, 230))
        
        bit_str = "".join(f"{b:08b}" for b in raw_payload)
        
        # Color segments
        # 0..6: LX (7), 7..13: LY (7), 14..20: RX (7), 21..27: RY (7), 28..31: BTN (4), 32..35: TL (4), 36..39: TR (4)
        bit_colors = (
            [CYAN] * 7 + [CYAN] * 7 + [AMBER] * 7 + [AMBER] * 7 + [RED] * 4 + [LIME] * 4 + [LIME] * 4
        )
        
        bx_bit = 520
        by_bit = 260
        for i, char in enumerate(bit_str):
            col = bit_colors[i] if i < len(bit_colors) else TEXT_MUTED
            c_surf = self.font_mono.render(char, True, col)
            self.screen.blit(c_surf, (bx_bit + i * 13, by_bit))
        
        legend = [
            ("ST_L_X (7b)", CYAN), ("ST_L_Y (7b)", CYAN), ("ST_R_X (7b)", AMBER), 
            ("ST_R_Y (7b)", AMBER), ("BUTTONS (4b)", RED), ("TRIGGERS (8b)", LIME)
        ]
        leg_x = 520
        leg_y = 285
        for name, col in legend:
            pygame.draw.rect(self.screen, col, (leg_x, leg_y + 4, 8, 8))
            s = self.font_sm.render(name, True, TEXT_MUTED)
            self.screen.blit(s, (leg_x + 14, leg_y))
            leg_x += s.get_width() + 26

        # Crypto State
        self.screen.blit(self.font_bold.render("SECURITY PIPELINE (SPECK64/128 CTR + CRC8):", True, TEXT_WHITE), (520, 335))
        nonce_val = ((self.session_id & 0xFFFFFFFF) << 32) | (self.seq_num & 0xFFFFFFFF)
        c1 = self.font_mono.render(f"Session ID : 0x{self.session_id:08X}   | Nonce: 0x{nonce_val:016X}", True, TEXT_WHITE)
        status_enc = "ENCRYPTED (CTR STREAM)" if self.encryption_enabled else "PLAINTEXT (BYPASSED)"
        enc_col = MAGENTA if self.encryption_enabled else AMBER
        c2 = self.font_mono.render(f"Cipher State: {status_enc}", True, enc_col)
        c3 = self.font_mono.render(f"Integrity   : CRC8 = 0x{crc:02X} (poly 0x07, Encrypt-then-MAC)", True, LIME)
        c4 = self.font_mono.render(f"Sequence Cnt: {self.seq_num} (reconstructs 32-bit counter)", True, CYAN)

        self.screen.blit(c1, (520, 360))
        self.screen.blit(c2, (520, 385))
        self.screen.blit(c3, (520, 410))
        self.screen.blit(c4, (520, 435))

        # ----------------------------------------------------------------------
        # Bottom Controls & Bar
        # ----------------------------------------------------------------------
        self.draw_panel((20, 550, 1060, 125), "CONTROLS & SHORTCUTS")

        btn_enc_col = MAGENTA if self.encryption_enabled else (33, 38, 45)
        pygame.draw.rect(self.screen, btn_enc_col, (40, 585, 230, 40), border_radius=6)
        txt_e = self.font_bold.render("[E] TOGGLE SPECK CRYPTO", True, TEXT_WHITE if self.encryption_enabled else TEXT_MUTED)
        self.screen.blit(txt_e, (52, 597))

        btn_demo_col = AMBER if self.demo_mode else (33, 38, 45)
        pygame.draw.rect(self.screen, btn_demo_col, (290, 585, 200, 40), border_radius=6)
        txt_d = self.font_bold.render("[SPACE] DEMO MODE", True, (0,0,0) if self.demo_mode else TEXT_MUTED)
        self.screen.blit(txt_d, (315, 597))

        txt_keys = self.font_mono.render("Keys: [1-7] Select Mode | [R] Reset Seq Num | [Click] Drag Sticks / Buttons", True, TEXT_MUTED)
        self.screen.blit(txt_keys, (520, 598))

        mode_str = f"CURRENT MODE: {self.mode}"
        self.screen.blit(self.font_bold.render(mode_str, True, PURPLE), (520, 625))

        fps_str = f"LOOP: {self.clock.get_fps():0.1f} FPS | OTA SIZE: 8 BYTES"
        self.screen.blit(self.font_mono.render(fps_str, True, TEXT_MUTED), (820, 625))

        pygame.display.flip()
        self.seq_num = (self.seq_num + 1) & 0xFFFFFFFF

    def run(self):
        t0 = time.time()
        running = True
        while running:
            running = self.handle_events()
            t = time.time() - t0
            self.update_inputs(t)
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()

if __name__ == "__main__":
    app = RFBPVisualizer()
    app.run()
