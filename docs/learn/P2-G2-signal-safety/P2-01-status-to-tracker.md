# P2-01 ย้ายสถานะงานไปไว้ใน GitHub issues

> Phase P2 (M2 Signal Safety + Controller Contract) · Gate G2 · Ticket P2-01 · Issue #14 · Slice: ไม่มี · Decisions: ไม่มี

## ทำไม

ตอนนี้คำถาม "งานถึงไหนแล้ว" มีคำตอบอยู่ **สี่ที่** และไม่มีอะไรบังคับให้ทั้งสี่ตรงกัน:

| ที่ | บอกอะไร |
|---|---|
| `docs/DIRECTION.md` §1 | milestone ปัจจุบัน และ plan ไฟล์ไหนคือ "ปัจจุบัน" |
| `docs/DIRECTION.md` §2 | ladder M0–M9 และคอลัมน์ State (done / current) |
| status line ใน plan file | สถานะของแต่ละ Task (`status: todo`) |
| GitHub milestone และ issue | สถานะของแต่ละ ticket (#14–#19) ตั้งแต่ PR #20 |

ตัวอย่างจริงตอนนี้: `DIRECTION.md` §1 ยังชี้ไปที่ `docs/plans/2026-09-06-m2-signal-plan-and-executor.md`
และบอกว่า Task 5 เป็น `todo` ในขณะเดียวกัน GitHub ก็บอกว่า #15 (P2-02 ซึ่งก็คือ Task 5) เปิดอยู่
ทั้งสองที่ยังพูดตรงกัน แต่พอเริ่มทำ P2-02 จะต้องเปลี่ยนสถานะสองที่พร้อมกัน ถ้าลืมที่ใดที่หนึ่ง
ข้อมูลก็จะขัดกันทันที

## ทำงานยังไง

หลัง ticket นี้ จะเหลือแค่สองที่ และแต่ละที่มีหน้าที่ไม่ซ้อนกัน:

- **`docs/roadmap/cadence.md`** เป็น **definition**: แต่ละ phase และ ticket คืออะไร, เสร็จเมื่อไหร่,
  อะไรบล็อกอะไร ไม่มีสถานะในไฟล์นี้
- **GitHub** เป็น **สถานะ**: milestone `P2 …` มี progress bar ส่วน issue เปิดหรือปิดบอกว่า ticket
  เสร็จหรือยัง

ของเดิมที่จะถูกลบ:
- `tools/plan_status.py`, `make status` และ `tests/test_plan_status.py` คือระบบที่อ่าน status line
  จาก plan
- SessionStart hook ที่พิมพ์ตารางสถานะตอนเปิด session (คำถามข้อหนึ่งของ ticket นี้คือจะมีอะไรมาแทน)
- M2 plan เก่าและ program map ซึ่งเนื้อหาที่ยังต้องใช้ย้ายเข้า roadmap ไปแล้วตอน `/menu`
- `DIRECTION.md` §1–§2 จะเหลือแค่ pointer ไปที่ roadmap

## ศัพท์

- **roadmap**: ไฟล์ที่นิยาม phase และ ticket ทั้งโปรเจกต์ (`docs/roadmap/cadence.md`)
- **phase `P<n>`**: เท่ากับ milestone `M<n>` เช่น P2 คือ M2
- **ticket `P<n>-<nn>`**: งานหนึ่งชิ้นที่ส่งมอบได้ มี issue ของตัวเองหนึ่งใบ
- **status line**: บรรทัด `status: todo | doing | done` ใต้หัวข้อ Task ใน plan file เป็นระบบเดิม
  ที่ ticket นี้จะเอาออก
- **GitHub milestone**: กลุ่มของ issue ใน GitHub มีหนึ่งกลุ่มต่อหนึ่ง phase
