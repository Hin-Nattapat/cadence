# P2-03 ให้ executor ขับไฟบนการรันจริง

> Phase P2 (M2 Signal Safety + Controller Contract) · Gate G2 · Ticket P2-03 · Issue #16 · Slice: ไม่มี · Decisions: `SIG-D01`, `SIG-D03`, `SIG-D04`, `SIM-D01`, `SIM-D02`, `SIM-D03`

## ทำไม

ถึงตอนนี้ executor (ตัวตัดสินว่าเปลี่ยนไฟได้เมื่อไหร่) ผ่านการทดสอบกับ SUMO ปลอมเท่านั้น ส่วนท่อที่ส่งคำสั่งเข้า
SUMO (`signal_writer`, P2-02) ก็ทดสอบแยกชิ้น ยังไม่เคยมีการรันจริงสักครั้งที่ executor เป็นคนคุมไฟตั้งแต่ต้นจนจบ
ticket นี้ต่อทุกชิ้นเข้าด้วยกันบนการรันจริงของ `s0_turning` แล้วพิสูจน์ว่าการเปลี่ยนไฟ **ปลอดภัย**

ยังไม่มีตัวควบคุม (นั่นคือ P2-04) จึงใช้ **request schedule** แทน คือรายการ "วินาทีที่ t ให้ขอ stage นี้ที่แยกนี้"
เช่น `(20.0, A0, 2)` แปลว่าวินาทีที่ 20 ให้ขอ stage 2 ที่แยก `A0`

## สิ่งที่ prototype วัดได้แล้ว

ผมรัน executor ต่อเข้ากับ SUMO จริงบน `s0_turning` เป็นเวลา 600 วินาที ทั้ง traci และ libsumo โดยขอ stage 2 ที่ t=20
แล้วปล่อยให้ max green บังคับวนไปเรื่อย ๆ ผลออกมาเหมือนกันทั้งสอง binding:

| t | phase ที่ SUMO รายงาน | elapsed | executor สั่ง |
|---|---|---|---|
| 20 | 0 | 20 | `SetPhase(1)` เข้าไฟเหลือง |
| 21–22 | 1 | 1–2 | – |
| 23 | 1 | 3 | `SetPhase(2)` + ยืดเวลา 61 s |
| 24 | 2 | 1 | – |
| 83 | 2 | 60 | `SetPhase(3)` (ถูกบังคับเพราะครบ max green) |
| 86 | 3 | 3 | `SetPhase(0)` + ยืดเวลา 61 s |

- ไฟเหลืองอยู่ครบ 3 วินาทีทุกครั้ง ไม่ยาวกว่าและไม่สั้นกว่า
- stage อยู่ได้ไม่เกิน 60 วินาที (max green)
- ตลอด 600 วินาที executor กับ SUMO ไม่เคยเห็นไม่ตรงกัน (`_reconcile` ไม่เคย raise)

## Zero-margin race คืออะไร และคำตอบ

ไฟเหลือง phase 1 ยาว 3 วินาทีตาม program ดังนั้นที่ t=23 นาฬิกาของ SUMO เองก็หมดพอดีเหมือนกัน คำถามคือ
**ใครเปลี่ยนไฟก่อน**: SUMO เปลี่ยนเองตาม program หรือ `SetPhase(2)` ของ executor ถ้า SUMO ชนะ executor
จะตามหลัง SUMO หนึ่ง step โดยไม่มีใครรู้ เพราะช่องว่างที่ `_reconcile` ยอมได้คือหนึ่ง step พอดี

คำตอบจาก prototype: **executor ชนะเสมอ** ที่ t=23 SUMO ยังรายงาน phase 1 elapsed 3 แล้วคำสั่ง `SetPhase(2)`
ก็ถูกส่งก่อน `simulationStep` ถัดไป SUMO จึงไม่ได้เปลี่ยนไฟเองเลย ไม่ต้องสั่งเร็วขึ้นหนึ่ง step และไม่ต้องยืดเวลา
ไฟเหลืองด้วย ผลนี้ตรงกับที่ P2-02 วัดไว้ว่า SUMO เปลี่ยนไฟ "หลังจาก" เวลาหมดไปแล้วหนึ่ง step ticket นี้จะบันทึกคำตอบเป็น
decision ใหม่ (`SIM-D`) และเขียนเป็น test ด้วย

## "ปลอดภัย" วัดยังไง

roadmap เขียนว่า "ไม่มี emergency stop" ซึ่งหมายถึงรายการที่ SUMO ให้มา (`getEmergencyStoppingVehiclesIDList`)
แต่ prototype พบว่า **รายการนี้ว่างเสมอบน s0** แม้จะเปลี่ยนจากเขียวเป็นแดงทันทีแบบไม่มีไฟเหลืองก็ตาม:

| การรัน | เบรกแรงสุด (m/s²) | จำนวนครั้งที่เบรกแรงเกิน `decel` ของรถ | emergency stop ของ SUMO |
|---|---|---|---|
| `none` (program เดิม) | −4.5 | 0 | 0 |
| executor + schedule | −4.5 | 0 | 0 |
| เปลี่ยนไฟแบบดิบ ไม่มีไฟเหลือง | −6.07 | 2 | 0 |

รถใน s0 มี `decel = 4.5` (เบรกปกติที่รถยอมใช้) แต่ SUMO จะนับเป็น emergency stop ก็ต่อเมื่อเบรกถึง
`emergencyDecel` (ค่าเริ่มต้น 9 m/s²) การเปลี่ยนไฟแบบดิบสิบครั้งทำให้รถต้องเบรกแรงกว่าปกติ (−6.07) แต่ยังไม่ถึงระดับนั้น

### ตัวนับของ SUMO ใช้งานได้จริงไหม: ทดลองให้มันนับ

เพื่อพิสูจน์ว่าตัวนับไม่ได้ว่างเพราะเสีย ได้ทดลองสามแบบ ผลตรงกันทั้ง traci และ libsumo:

| การทดลอง | emergency stop ของ SUMO | เบรกแรงสุด (m/s²) |
|---|---|---|
| s0 จริง สลับ stage 0 ↔ 2 แบบดิบทุก 2 วินาที (ไม่มีไฟเหลือง) | **27** | −9.0 |
| s0 จริง เปลี่ยนเป็นไฟแดงทุกทิศทันที ทุก 30 วินาที | **3** | −9.0 |
| s0 ฉบับก๊อปปี้ที่ตั้ง `emergencyDecel = 5.0`, ไม่ยุ่งกับไฟ | 0 | −4.5 |
| s0 ฉบับก๊อปปี้ที่ตั้ง `emergencyDecel = 5.0`, เปลี่ยนแบบดิบสิบครั้ง | **2** | −5.0 |

สรุป:
- ตัวนับของ SUMO **ทำงานจริง** มันนับเมื่อรถเบรกถึง `emergencyDecel` พอดี (−9.0 บน s0 จริง, −5.0 บนฉบับก๊อปปี้)
- การสลับไฟถี่ ๆ แบบไม่มีไฟเหลืองทำให้รถชนกันจนถูก teleport ด้วย นี่คือสิ่งที่ safety layer มีไว้ป้องกัน
- บนฉบับก๊อปปี้ จำนวนที่นับได้ (2) เท่ากับจำนวนครั้งที่ "เบรกแรงเกิน `decel`" ใน s0 จริง แปลว่า hard braking
  (ตัววัดที่เราคิดขึ้น) คือเหตุการณ์เดียวกัน เพียงแต่ใช้เกณฑ์ที่เข้มกว่า

สองตัววัดนี้จึงต่างกันแค่เกณฑ์:
- **emergency stop ของ SUMO**: เกณฑ์คือ `emergencyDecel` เป็นนิยามของ SUMO เอง
- **hard braking**: เกณฑ์คือ `decel` ของรถ เข้มกว่า จับการเปลี่ยนไฟที่กะทันหันแต่ยังไม่ถึงขั้นฉุกเฉินได้

### เลือกใช้ hard braking ตัวเดียว

- SUMO บังคับ `emergencyDecel ≥ decel` เสมอ ถ้า hard braking เป็น 0 emergency stop ก็ต้องเป็น 0 ด้วย การ assert
  ทั้งสองตัวจึงซ้ำกัน
- hard braking ใกล้กับคำถามจริงของ safety layer มากกว่า คำถามนั้นคือ "ไฟเหลืองนานพอให้หยุดได้แบบปกติหรือไม่" ซึ่งเป็นหลักที่ใช้ออกแบบ
  เวลาไฟเหลืองในทางวิศวกรรมจราจร ส่วน emergency stop ถามแค่ว่า "เกือบชนหรือยัง"
- **ข้อจำกัด**: บน s0 การรัน `none` มี hard braking เป็น 0 จึงใช้ได้ตรง ๆ แต่ในฉากที่รถติด (P7, P8) รถอาจเบรกแรง
  เพราะรถคันหน้า ไม่ใช่เพราะไฟ ถึงตอนนั้นต้องจำกัดให้นับเฉพาะรถที่กำลังเข้าแยกตอนไฟเปลี่ยน
- `decel` ของ SUMO (4.5 m/s² ใน s0) แรงกว่าค่า "หยุดสบาย" ที่ใช้ออกแบบไฟเหลือง เกณฑ์นี้จึงยังหลวมกว่าทางวิศวกรรมอยู่บ้าง

## ทำงานยังไง

- `run_scenario` รับ request schedule ได้ (ไม่บังคับ) ถ้ามี schedule จะสร้าง plan จาก `signal_plan.yaml`
  สร้าง executor หนึ่งตัวต่อแยก แล้วทุก step จะ tick ส่งคำสั่งผ่าน `connection.apply_signal_commands` และบันทึก event
  ผ่าน `recorder.record_signal_events` ส่วนการรันที่ไม่มี schedule คือ `none` เหมือนเดิมทุกไบต์
- test พิสูจน์สี่เรื่อง:
  1. **signal transition**: ขอ stage 2 ที่ t=20 แล้วได้ไฟเหลืองครบเวลาตาม program จากนั้นเข้า stage 2 ตรง step ที่ executor บอก
     และมี event `stage_requested`, `transition_started`, `stage_entered`
  2. **ไม่มีการเบรกแรงเกินเหตุ** เมื่อ executor คุม แต่เส้นทางดิบ (สั่ง `SetPhase` ข้ามไฟเหลือง) มี
  3. **elapsed bound**: `phase_elapsed_s` ไม่เกิน max green + หนึ่ง step ใน stage และไม่เกินเวลาของไฟเหลืองใน transition
  4. program แบบ `actuated` (เปลี่ยนไฟเองได้) ถูกปฏิเสธก่อน tick แรก
- `docs/CODEBASE.md` (ภาษาไทย) เพิ่ม `control/` และตาราง `signal_event`

## Decisions ที่ ticket นี้ยืนอยู่

- **`SIG-D01`** เปลี่ยนไฟด้วยการเลือก phase ใน program เดิม (`setPhase`) ไม่สร้างสตริงไฟเอง จึงไม่เกิด program
  "online" ของ SUMO และ `phase_index` / `phase_elapsed_s` ที่อ่านได้ยังบอกความจริง
- **`SIG-D03`** stage คือ phase ที่ให้รถวิ่งได้และไม่มีเหลือง ไฟเหลืองขอไม่ได้
- **`SIG-D04`** executor คืนคำสั่งเป็นข้อมูล และมีจุดเดียวที่เขียนเข้า SUMO
- **`SIM-D01`** (วัดไว้แล้ว) ถ้าใช้ `setRedYellowGreenState` SUMO จะเปลี่ยนเป็น program "online" ทำให้ `getPhase` ค้าง
  นี่คือเหตุผลของ `SIG-D01`
- **`SIM-D02`** (วัดไว้แล้ว) `setPhase` มีผลใน step เดียวกันและเริ่มนาฬิกาของ phase ใหม่ ส่วน `setPhaseDuration` ตั้งเวลาที่เหลือครั้งเดียว
- **`SIM-D03`** (ยังเป็นสมมติฐาน) traci กับ libsumo ให้ผลเหมือนกันภายใต้ลำดับการเขียนเดียวกัน จะยกเป็น adopted ได้เมื่อ
  การรันที่มีตัวควบคุมทั้งรอบตรงกันทุกไบต์ (P2-04)

## ศัพท์

- **request schedule**: รายการ `(time_s, intersection_id, phase_id)` ที่ใช้แทนตัวควบคุมชั่วคราว
- **tick**: การเรียก executor หนึ่งครั้งต่อหนึ่ง step หลัง SUMO เดินไปแล้ว
- **reconcile**: ขั้นแรกของ tick ที่เช็กว่า phase และนาฬิกาที่ SUMO รายงานตรงกับที่ executor คิด ถ้าไม่ตรงจะ raise
- **zero-margin race**: step ที่นาฬิกาไฟเหลืองของ SUMO หมดพร้อมกับที่ executor สั่งเปลี่ยน ใครชนะ
- **hard braking**: รถเบรกแรงกว่า `decel` ของมันเอง เป็นสัญญาณว่าไฟเปลี่ยนกะทันหันเกินไป
- **emergency stop (ของ SUMO)**: การเบรกที่แรงถึงระดับ `emergencyDecel` ซึ่งแรงกว่า hard braking มาก
- **actuated program**: program ที่ SUMO ปรับเวลาเองตามรถที่ตรวจจับได้ ใช้กับ executor ไม่ได้ เพราะ SUMO จะเปลี่ยนไฟเองโดยไม่ได้รับคำสั่ง

## สิ่งที่สร้างเสร็จแล้ว

- `run_scenario(..., request_schedule=...)` ใน `cli.py` รับรายการ `ScheduledRequest(time_s, intersection_id, phase_id)`
  - ถ้าไม่ส่ง (`None`) ผลการรันจะเหมือนการรัน `none` เดิมทุกไบต์ ยืนยันด้วย golden test ที่ผ่าน
  - ถ้าส่ง ระบบจะสร้าง plan กับ executor ของทุกแยก แล้วสั่ง tick ทุก step รวมถึง step แรก
    event ที่ได้จะถูกเขียนลง `state/signal_event.parquet`
  - manifest และชื่อโฟลเดอร์การรันจะมี `request_schedule` / `v1`
- `start_executors` กับ `tick_executors` คือขั้นควบคุมหนึ่ง step ทั้ง `run_scenario` และ test ความปลอดภัยเรียกฟังก์ชันชุดเดียวกันนี้
  `tick_executors` ไล่แยกตามลำดับ `IntersectionId`
- คำขอจะ "ถึงเวลา" ที่ step แรกที่ `now_s ≥ time_s` และส่งให้ executor แค่ครั้งเดียว
  ถ้าแยกเดียวกันมีหลายคำขอถึงเวลาพร้อมกัน จะส่งคำขอที่ถึงก่อนไปก่อนหนึ่งคำขอ ที่เหลือรอส่งใน step ถัด ๆ ไป ไม่มีคำขอไหนหายไป
- schedule ที่ใช้ไม่ได้จะถูกปฏิเสธด้วย `ValueError` ก่อน tick แรก มีสามกรณี:
  - ฉากไม่มี `signal_plan.yaml`
  - คำขอระบุแยกที่ไม่มี plan
  - program ไม่ใช่แบบ `static`

  เมื่อถูกปฏิเสธ จะไม่มีโฟลเดอร์การรันค้างอยู่ใน output
- `SumoConnection.hard_braking_vehicles()` คืนรายการรถที่ step ล่าสุดเบรกแรงกว่า `decel` ของตัวเอง
  ค่านี้มีไว้อ่านใน test เท่านั้น ไม่ได้บันทึกลงไฟล์การรัน
- ลงทะเบียน `SIM-D04` แล้ว: executor ชนะ zero-margin race

## สิ่งที่วัดได้จากการรันจริง

ทุกข้อด้านล่างได้ผลเหมือนกันทั้ง traci และ libsumo บน `s0_turning` seed 1

- **ขอ stage 2 ตอน t=20:**
  - phase ที่อ่านได้ตอน t = 20, 21, 22, 23, 24 คือ 0, 1, 1, 1, 2 แปลว่าได้ไฟเหลืองครบ 3 วินาทีก่อนเข้า stage
  - event ที่เกิดคือ `stage_requested` และ `transition_started` ตอน 20 แล้ว `stage_entered` ตอน 23
- **ตลอด 600 s:**
  - ทุกช่วงไฟเหลืองที่ครบช่วงยาวเท่ากับระยะเวลาใน program พอดี มีอย่างน้อย 5 ช่วง
  - stage ไม่เคยค้างเกิน `max_green_s + step_length_s` (61 s) และมีอย่างน้อยหนึ่ง stage ที่ค้างถึง 60 s
  - reconcile ไม่เคย raise
- **สลับ stage 10 ครั้ง (`SWITCH_TIMES_S`):**
  - ถ้าสลับผ่าน executor ไม่มีรถเบรกแรงเลยสักคันตลอดการรัน
  - ถ้าใช้ `SetPhase` ตรง ๆ ข้ามไฟเหลือง จะมีรถเบรกแรง แปลว่า test นี้ fail ได้จริง

## รันและตรวจยังไง

```
rtk proxy make check
uv run pytest tests/simulation/sumo/test_signal_transition.py -q   # การรันที่มี schedule อ่านผลจากโฟลเดอร์การรัน
uv run pytest tests/simulation/sumo/test_signal_safety.py -q       # ไม่มีเบรกแรงตอน executor ขับ, มีตอนสลับดิบ
uv run pytest tests/test_cli.py -q -k "schedule or due"            # การปฏิเสธสามแบบ + ลำดับคิวคำขอ
uv run pytest tests/simulation/sumo/test_golden.py -q              # การรัน none ยังตรง golden
```

## ยังไม่ได้ทำ และขั้นต่อไป

- `cadence run` ยังไม่มี flag สำหรับ schedule ตอนนี้ส่ง schedule ได้ผ่าน `run_scenario` ใน Python เท่านั้น
- manifest ยังแยกไม่ออกว่าสองการรันใช้ schedule ต่างกันหรือเปล่า เพราะยังไม่มี digest ของ config ซึ่งจะมาใน P2-06 (`controller_config_sha256`)
- schedule ไม่ตรวจค่า `time_s` แปลก ๆ:
  - ถ้าเป็น NaN คำขอนั้นจะไม่ถึงเวลาเลย และคำขอที่ตามหลังในแยกเดียวกันก็จะไม่ถูกส่งไปด้วย
  - ถ้าเลยเวลาจบการรัน คำขอนั้นจะไม่ถูกส่งเลย
  - ยอมรับข้อจำกัดนี้ไว้ เพราะ schedule เป็นแค่โครงชั่วคราวที่ P2-04 จะเอา controller มาแทน
- hard braking อาจนับผิดเมื่อรถติดหนัก (P7/P8) และ `decel` 4.5 ยังหลวมกว่าเกณฑ์ราว 3 m/s² ของ ITE ดูหัวข้อ "เลือกใช้ hard braking ตัวเดียว" ด้านบน
- `SIM-D03` ยังเป็นสมมติฐานอยู่ จะได้คำตอบตอนที่ controller ตัวจริงรันครบใน P2-04
- ขั้นต่อไปคือ **P2-04**: lifecycle ของ controller กับ action v1 และ flag `--controller` ซึ่งจะมาแทน request schedule
