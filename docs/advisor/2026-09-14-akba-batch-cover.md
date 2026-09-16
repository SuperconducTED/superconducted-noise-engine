# Danışman toplu mesajı (2026-09-14)

> **NOTE · What this file is.** The **exact plain-text e-mail to be sent** to Dr. Fırat
> Akba for Issue #56 FR-12's single batched advisor request. It is committed so the
> repository records what was circulated, not only that something was. The body below is
> the message verbatim: if what actually goes out differs from it in any way, this file is
> wrong and gets corrected, not the other way round. **As of this commit it has not been
> sent.**
>
> **NOTE · Nothing is attached.** The six HTML files of
> `docs/advisor/2026-09-09-akba-brief/` are **internal working documents and are not sent.**
> They were originally drafted as an attachment cluster; that plan was dropped on
> 2026-09-14, before anything went out, in favour of one self-contained plain-text message.
> Sending six styled HTML files to someone who has never answered a question from this
> project asks him to open an archive before he can read a sentence. The cluster keeps its
> value as the place each question's full argument is worked out, and this message is what
> he actually receives. Where the cluster's own decision calendar disagrees with the dates
> below, the decisions register's `## Circulation, as-of 2026-09-14` section is
> authoritative.
>
> **NOTE · Written 2026-09-14, send recorded separately.** The send date and medium are
> appended to `docs/advisor/2026-09-03-decisions-from-akba.md` once the message has
> actually gone out. **Nothing here asserts a send.**
>
> **NOTE · Every figure below is sourced.** 1123 documents / 601 distinct states /
> 46.5% duplication and the 29 November projection are `health/metrics.json` on
> `calibration-data` @ `272a0c5`, generated 2026-09-14T09:03:34Z. The floor of 1170 and the
> 234 parameter count are NC-045; the seven-shape spread including IntervalGaussianMF's 243
> is NC-046; the 616 tests are NC-021 at `main` @ `125b796`. The 37 / 35 merged-PR counts
> were re-run today with `gh pr list --state merged` filtered to `mergedAt >= 2026-05-25`,
> per the cycle-2 close record's instruction that the count be re-measured rather than
> carried. The 11-of-26 Open/Deferred figure is a count of `**Status**` lines in
> `docs/decisions.md` at `004e14e`.
>
> **NOTE · The 29 November projection is deliberately not registered.** ADR-025's
> amendment makes `projected_date` a non-registrable extrapolation, so it carries no NC row
> and the message labels it a tahmin rather than an ölçüm. It is included because the
> advisor is being asked about publication timing, and withholding the one number that
> bears on it would be asking him to decide with less than we know.

## Twelve register items, fourteen questions

The decisions register carries **12 live items**; this message asks **14 questions**. The
counts differ on purpose and the mapping is one-to-one in both directions, so no item is
dropped and no question is invented:

| Register item | Question(s) | Note |
| --- | --- | --- |
| 1 · ADR-027 target (D1, D3, D4) | **1, 2, 3** | Split. One item in the register, three genuinely separate decisions: the damping formula, the qubit rejection rule, and averaging per-qubit targets rather than evaluating at mean T1/T2. Asking them as one question invites one answer covering whichever he read first. |
| 2 · ADR-025 `duplicate-partial` | 4 | |
| 10 · `TSKTrainer` owner read | 5 | Covers `types.py`'s four value types too, as File 01's D5 does. |
| 12 · `MembershipFunction` docstring | 6 | |
| 3 · ADR-009 | 7 | |
| 4 · ADR-011 | 8 | |
| 6 · ADR-015 | 9 | |
| 8 · ADR-019 closure | 10 | |
| 14 · ADR-025 pipeline-health | 11 | |
| 13 · the ten 2026-05-25 questions | **12** | Merged. Six are still open (Q1, Q3, Q5, Q6, Q8, Q9) and ride as one question with six clauses, because they are one conversation about what the field expects. Q2, Q4, Q7 and Q10 are answered in practice by the phase-3 plan and are not re-asked. |
| 5 · ADR-014 status flip | 13 | |
| 7 · ADR-016 | 14 | |

The withdrawn items (1b, 9, 11) appear nowhere in the message, which is the point of
withdrawing them. Their reasons stay recorded in the register.

---

```text
Konu: SuperconducTED / Faz 3 durumu ve karar bekleyen maddeler


Fırat Hocam merhaba,

Projede Eylül sonuna kadar sürecek bir "Faz 3" tanımladık ve hedefi net: eğitilmiş
bir modelin karşılaştırma tablosu. O tablonun çıkabilmesi için sizin kararınıza
bağlı 14 soru var ve bunları tek tek değil, tek mesajda soruyorum. Sebebi şu: 25
Mayıs'ta hazırladığımız on soruluk listenin hiçbirine kayıtlı bir cevap yok ve o
liste soruları on üç ayrı yere dağıttığımız için kayboldu. Bu sefer hepsi burada,
her maddenin bir tarihi var.

Aşağıdaki sayıların hepsi bugün ölçüldü, hafızadan yazılmadı.


1) ŞU ANDA NEREDEYIZ

- Arşiv: 1123 kalibrasyon dokümanı, bunların 601'i ayrık cihaz durumu
  (14 Eylül 09:03 UTC itibarıyla). Tekrar oranı yüzde 46,5.
- Eğitim eşiği: 1170 ayrık durum. Yani eşiğin yüzde 51'indeyiz.
- Parametre başına örnek: 2,57. Gereken 5.
- Test paketi: 616 test, hepsi geçiyor.
- Boru hattı uçtan uca çalışıyor; eksik olan eğitim, ölçüm değil.

Mevcut hızla (son 30 günde 161 yeni durum, günde ~5,4) eşiği yaklaşık 29 Kasım'da
geçiyoruz. Bu bir tahmin, ölçüm değil, ve bilerek hiçbir yere resmi olarak
kaydetmiyoruz; ama Faz 3'ün 30 Eylül bitişinden iki ay sonrasına düştüğü için
size söylemem gerek.


2) 25 MAYIS'TAN BU YANA NE YAPTIK

- 37 pull request birleşti, 35'i ana dala.
- Kalibrasyon arşivi ve onun bütünlük altyapısı: saatlik toplayıcı, kayıp
  pencereleri geri dolduran mekanizma, ve her dokümanın ne olduğunu yazan bir
  defter.
- Sayısal iddia kaydı: projedeki her sayı artık bir satıra ve o satırın ölçüldüğü
  commit'e bağlı. Uydurma rakam üretemiyoruz, bu kasıtlı bir kısıt.
- Eğitim sözleşmesi: eğitici için soyut sınıf, değer tipleri, ve hedef formülü
  (ADR-027, sizin onayınızı bekliyor).
- Yedi üyelik fonksiyonu şeklinin tamamı için parametre sayımı ve kıyaslama
  altyapısı.


3) EN ÖNEMLİ BULGU: EĞİTİM EŞİĞİ YANLIŞTI

Bu maddeyi ayrı yazıyorum çünkü aleyhimize bir düzeltme.

Eşiği "yaklaşık 126 eğitilebilir parametre x 5 = 630" diye taşıyorduk. 126'yı
hiçbir dosya türetmemiş; 7 Mayıs'ta bir cümleye girmiş ve o tarihte 27 kurallı
ızgara henüz yokmuş. Kural tabanına sorduk: gerçek sayı 234, çünkü 126 iki
çıkışlı bir modelin sonuç terimini tek çıkış üzerinden sayıyor.

Yani eşik 630 değil 1170. Daha önce "eşiği geçemedik" diyen her belge hala doğru,
ama açık iki kat daha büyük.

Bunun yan ürünü sizin ADR-009 kararınızı doğrudan ilgilendiriyor: Aralık Tip-2'nin
parametre sayısını ikiye katladığı itirazı bu yapılandırmada geçerli değil.
IntervalGaussianMF 243, GaussianMF 234, yani 9 parametre fark, yüzde 3,8. Sebep,
IT2'nin benzersiz üyelik fonksiyonu nesnesi başına bir parametre eklemesi ve
burada sadece 9 nesne olması.


4) EKSİK OLANLAR

- Eğitici henüz yazılmadı; Faz 3'ün en uzun kalemi ve başlamadı.
- Üyelik fonksiyonu şekil karşılaştırması (ablasyon) çalıştırılmadı.
- Tip sistemi kararı alınmadığı için ondan sonra gelen üç karar da bekliyor.
- 26 karar kaydının 11'i hala "Open" ya da "Deferred". Bunların yedisi doğrudan
  sizin kararınıza bağlı (ADR-009, 011, 014, 015, 016, 019, 027), artı ADR-025'in
  eki.
- Projenin başından bu yana kayda geçmiş tek bir danışman kararı yok. Eksiğin
  kaynağı bu.


5) SORULAR

Her madde tek cümle. Ayrıntısını isterseniz o maddeyi ayrıca açarım.

21 EYLÜL'E KADAR

1. Eğitim hedefi olarak T1, T2 ve kapı süresinden türettiğimiz iki sönümleme
   oranı formülünü onaylıyor musunuz (ADR-027)?
2. Eksik alanlı kübitleri hedeften eleme kuralımız ve elenenlerin tabloda NaN
   olarak yerinde bırakılması sizce doğru mu?
3. Anlık görüntü hedefi olarak kübit hedeflerinin ortalamasını alıyoruz, ortalama
   T1/T2'de hesaplamıyoruz; bu tercihi onaylıyor musunuz?
4. Bir kalibrasyon kaydını geri doldururken daha eksik gelen kopyayı "kısmi
   tekrar" sayıp atmamız sizce kabul edilebilir mi (ADR-025)?
5. interfaces.py ve types.py sizin dosyalarınız; eğitici soyut sınıfını ve dört
   değer tipini sahibi olarak bir gözden geçirir misiniz?
6. Aynı dosyada eğiticinin hangi modülde yaşadığını söyleyen tek satırlık bir
   belge düzeltmesi yaptık, onu da onaylar mısınız?

23 EYLÜL'E KADAR

7. Tip-1 mi Aralık Tip-2 mi ilerliyoruz (ADR-009)?
8. Durulaştırmada Nie-Tan kapalı formu mu, Karnik-Mendel yinelemeli indirgeme mi
   (ADR-011)?
9. Topluluk üyeleri birbirinden hangi mekanizmayla farklılaşsın (ADR-015)?
10. Ablasyon kazananını ADR-019'un kapanış kararı olarak kabul edecek misiniz?
11. Bir "cihaz durumu" ölçülen değerleriyle mi tanımlansın, ölçüm damgasıyla mı?
12. Eski listeden altı soru hala açık: topluluk yaklaşımı mimari olarak yeterli
    mi, metrik sıralaması ne olmalı, eksik kalibrasyon verisinde atlama mı bulanık
    maksimum entropi mi, hangi mecraya ne zaman gidiyoruz, tek arka uçtan
    çıkmalı mıyız, ve gerçek donanım doğrulaması ne kadar şart?

26 VE 30 EYLÜL

13. Eğitici M3'te birleştiğinde ADR-014'ü "Accepted" yapmayı onaylar mısınız
    (26 Eylül)?
14. Sonuçları tek sayı olarak mı yoksa üyeler arası aralık olarak mı raporlayalım
    (ADR-016, 30 Eylül)?

Vaktiniz kısıtlıysa 12. maddedeki yayın soruları en kritiği: cevabı bizde
olmayan ve deneyle üretemeyeceğimiz tek grup o.


Cevaplarınızı depoda tarihli bir kayda geçiriyorum: soru, cevabınız, tarih, ve
hangi kararı açtığı. Bir maddenin tarihinde cevapsız kalması sorun değil; o zaman
ilgili karar "Open" kalır ve sorunun hangi tarihte gittiğini yazarız.

Teşekkürler, iyi çalışmalar.

Mert Efe Şensoy
```
