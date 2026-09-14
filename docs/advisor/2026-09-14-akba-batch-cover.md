# Danışman toplu mesajı, kapak yazısı (2026-09-14)

> **NOTE · What this file is.** The Turkish cover message for the single batched advisor
> request of Issue #56 FR-12. It is the text @mertefesensoy pastes into the message he
> sends Dr. Akba; the six HTML files of `docs/advisor/2026-09-09-akba-brief/` ride with it
> unchanged. It is committed so the repository records what was circulated, not only that
> something was.
>
> **NOTE · This cover does not edit the 2026-09-09 cluster.** The cluster is a dated
> document. Where a date in its own decision calendar is superseded, this file says so and
> the cluster stays exactly as written. The authority for a decision-by date is
> `docs/advisor/2026-09-03-decisions-from-akba.md`, its `## Circulation, as-of 2026-09-14`
> section.
>
> **NOTE · Written 2026-09-14, sent separately.** The send date is appended to the
> decisions register once the message actually goes out. Nothing here asserts a send.

---

Sayın Hocam,

Bu mesaj Faz 3'ün açık kalan bütün danışman maddelerini **tek seferde** önünüze
koymak için yazıldı. Ekte altı dosyalık bir küme var; her dosya bir konu başlığını
arka planı, sorusu ve gerekçesiyle anlatıyor. Bu kapak yazısı da hangi maddenin
hangi dosyada olduğunu ve her biri için hangi tarihe kadar cevabınıza ihtiyacımız
olduğunu listeliyor.

Önce iki şeyi açıkça söylemem gerekiyor.

**Birincisi, bu mesaj gecikti.** Küme 9 Eylül'de hazırdı ve 14 Eylül'e kadar
gönderilmedi. Gecikme sizin tarafınızda değil bizim tarafımızda, ve bunu deponun
kaydına da böyle yazdık. Bunun sizin için tek pratik sonucu şu: ilk grup maddenin
tarihi 16 Eylül'dü, size iki gün kalırdı; onu 21 Eylül'e çektim ki gerçekten
okuyacak vaktiniz olsun. M3 kilometre taşına bağlı maddelerin 23 Eylül tarihini
ise **değiştirmedim**, çünkü o tarih bir hedef değil bir kapı: 23 Eylül'den sonra
gelen bir cevap o kararların bağlı olduğu işi artık açamıyor. Yani o gruptaki
pencere 14 günden 9 güne indi, ve bunun sebebi bizim gecikmemiz.

**İkincisi, size sormadıklarımız da bu mesajın parçası.** İlk listede on üç madde
vardı. Dördünü çıkardık: kendi ölçebileceğimiz ya da kendi aramızda çözmemiz
gereken şeylerdi. Çıkardıklarımızın gerekçesi ilgili dosyanın sonunda yazıyor.
Cevapsız kalan bir soru kadar, sorulmaması gereken bir soru da maliyetli, çünkü
bu projenin size açılan tek kanalı var.

Vaktiniz kısıtlıysa **Dosya 05 · Yayın stratejisi** ile başlayın. Diğer beş dosya
teknik onay niteliğinde ve hızlı okunur; 05'teki üç sorunun cevabı ise bu depoda
hiçbir yerde yok ve hiçbiri deneyle üretilemez.

---

## Maddeler, dosyaları ve karar tarihleri

Sınıflandırma: **SOR** = cevap sizde, ölçerek elde edemeyeceğimiz bir yargı ya da
yetki. **ONAYLA** = biz ölçtük, sizden tasarım değil teyit bekliyoruz.

### 21 Eylül'e kadar

| # | Madde | Sınıf | Dosya |
| --- | --- | --- | --- |
| 1 | ADR-027 eğitim hedefi, kararlar D1, D3, D4 | ONAYLA | Dosya 01 |
| 10 | `interfaces.py` ve `types.py`: `TSKTrainer` ile dört değer tipinin sahibi olarak okunması (D5) | SOR, yetki | Dosya 01 |
| 12 | `interfaces.py`: `MembershipFunction` belge dizesi düzeltmesinin sahibi olarak okunması | SOR, yetki | bu kapakta, aşağıda |
| 2 | ADR-025 `duplicate-partial` eki (PR #55'te borçlu) | SOR | Dosya 04 |

Bu grubun tarihi 16 Eylül'dü. Gecikme sebebiyle 21 Eylül'e alındı; içeriğin
hiçbirinde değişiklik yok.

### 23 Eylül'e kadar

Bu tarih **değişmedi**. M3 "kararlar" kilometre taşı 23 ile 25 Eylül arasında ve
bu maddelerin hepsi o kapıdan geçen işi açıyor.

| # | Madde | Sınıf | Dosya |
| --- | --- | --- | --- |
| 3 | ADR-009, Tip-1 mi Aralık Tip-2 mi | SOR kapsam, ONAYLA kanıt | Dosya 02 |
| 4 | ADR-011, Nie-Tan mı Karnik-Mendel mi | ONAYLA | Dosya 02 |
| 8 | ADR-019 kapanışı, ablasyon kazananı | ONAYLA | Dosya 02, Dosya 05 |
| 6 | ADR-015, topluluk üyelerinin nasıl farklılaşacağı | SOR | Dosya 03 |
| 14 | ADR-025 boru hattı eki, cihaz durumunun tanımı (PR #70'te borçlu) | SOR x2, ONAYLA x1 | Dosya 06 |
| 13 | 25 Mayıs 2026'nın on sorusundan açık kalan altısı: Q1, Q3, Q5, Q6, Q8, Q9 | karışık | Dosya 05, Dosya 04 |

On sorunun dördü (Q2, Q4, Q7, Q10) Faz 3 planı ve 7 Eylül'deki ADR-016
hizalamasıyla fiilen cevaplandı. Onları açıkta bırakmak yerine cevaplanmış olarak
işaretledik; hangi cevabın hangi soruya karşılık geldiği ilgili dosyada yazıyor.

### 26 Eylül'e kadar

| # | Madde | Sınıf | Dosya |
| --- | --- | --- | --- |
| 5 | ADR-014 durum değişikliği, Deferred'dan Accepted'a | ONAYLA | aşağıda, ayrı başlık |

Bu maddenin tarihi 30 Eylül'dü ve onu 26 Eylül'e çektim. Sebebi gecikme değil,
bir tutarsızlık: 30 Eylül fazın kapandığı gün, ve o gün gelen bir cevap o günkü
kapanış kaydını açamaz. Ayrıntısı aşağıda.

### 30 Eylül'e kadar

| # | Madde | Sınıf | Dosya |
| --- | --- | --- | --- |
| 7 | ADR-016, aralık birleştirme semantiği | SOR | Dosya 03 |

Bu maddenin ölçüm tarafını #64 yapıyor ve o iş zaten ayın son haftasında. Faz 3'ün
çıktı ürününü kilitlemediği için tarihi olduğu gibi bıraktım.

---

## Kümede karşılığı olmayan iki madde

Kapak yazısını hazırlarken kümeyi madde madde denetledim ve iki maddenin kayıt
defterinde tarihi olduğu halde hiçbir dosyada anlatılmadığını gördüm. İkisini de
uydurmak yerine burada, tam halleriyle soruyorum. Küme dosyalarına dokunmadım:
onlar 9 Eylül tarihli bir kayıt ve öyle kalıyor.

### Madde 12 · `MembershipFunction` belge dizesi düzeltmesi

**Arka plan.** `docs/team.md` sizi `src/superconducted/interfaces.py` dosyasının
birincil sahibi olarak kaydediyor. Dosya 01'deki D5 maddesi zaten o dosyayı
önünüze koyuyor, ama PR #69'un aynı dosyada yaptığı **üçüncü** değişikliği
adıyla anmıyor. O değişiklik şu:

`MembershipFunction` sınıfının belge dizesi, ANFIS eğiticisinin
`superconducted.fuzzy.tsk` modülünde yaşadığını söylüyordu. Bu iki şeyle
çelişiyordu: LOCKED olan o modülün kendi belge dizesi eğiticinin "kasten bu
modülde olmadığını" söylüyor, ve eğitim paketi kararı eğiticiyi
`superconducted.training` altına koyuyor. Tek satır düzeltildi ve bugün
`superconducted.training` diyor.

**Ne rica ediyoruz.** D5 için `interfaces.py` dosyasına zaten bakacaksınız; bu
satırı da o bakışın içine alın. Ölçülecek bir şey yok, bu bir yetki maddesi:
sahibi olduğunuz bir dosyada sizin okumanız olmadan bir satır değişti ve boşluğu
kapatmak istiyoruz.

### Madde 5 · ADR-014 durum değişikliği

**Arka plan.** ADR-014 bugün `Deferred`. Kendi metnindeki not, hiçbir eğitici
uygulamasının bu ADR altında kabul edilmediğini söylüyor. Faz 3'ün bitmesi için
o durumun `Accepted` olması gerekiyor, çünkü fazın çıktı ürünü eğitilmiş bir
modelin karşılaştırma tablosu ve o tablo ADR-014 altında yaşıyor.

**Ne rica ediyoruz.** Bugün cevaplayabileceğiniz bir soru **değil**, ve bunu
peşinen söylüyorum: onaylayacağınız şey henüz yok. Hibrit eğitici (#60) M3'te
tam döngüsüyle birleşecek, ilk arşiv uyumunu ve zaman bölmeli metriklerini
üretecek; ondan sonra ADR-014'ün durumu sizin onayınıza hazır olur. Bu maddeyi
kümeye şimdi koymamın sebebi tek: 26 Eylül'de size gelecek olan şeyin ne
olduğunu önceden bilmeniz, ve o tarihte hazırlıksız yakalanmamanız.

**Neden 30 değil de 26 Eylül.** Faz 3, 30 Eylül'de bir kapanış kaydıyla
kapanıyor ve o kayıt ADR-014'ün durumunu okuyor. Cevabın kapanış günü gelmesi,
kapanışın o cevabı taşıyamaması demek. Dört gün, hem eğiticinin M3'te birleşmesi
hem de kapanış kaydının cevabı taşıması için gereken en kısa aralık.

---

## Cevaplar nereye yazılıyor

Her cevap `docs/advisor/2026-09-03-decisions-from-akba.md` dosyasına bir tarihli
kayıt olarak ekleniyor: soru, cevabınız, cevabın verildiği tarih, hangi mecradan
geldiği, ve hangi PR'ı veya ADR'yi açtığı. Dosya yalnızca **ekleme** alıyor,
üstündeki hiçbir satır düzenlenmiyor.

Bir maddenin tarihinde cevapsız kalması bizim için sorun değil. Sorun, kayıtsız
kalması. Cevap gelmezse ilgili ADR `Open` kalır ve kayda sorunun hangi tarihte
gittiği yazılır, çünkü kaydedilmiş bir boşluk bir kayıttır, sessizlik değildir.

Kolay gelsin, teşekkürler.

Mert Efe Şensoy

---

## Ekler

| Dosya | Konu |
| --- | --- |
| `01-egitim-hedefi.html` | Eğitim hedefi, ADR-027, ve D5 sahiplik okuması |
| `02-tip-sistemi.html` | Tip sistemi, ADR-009 ve ADR-011, ADR-019 ablasyonu |
| `03-topluluk-ve-varyans.html` | Topluluk ve varyans, ADR-015 ve ADR-016 |
| `04-veri-durustlugu.html` | Veri dürüstlüğü, ADR-025 eki ve eksik veri |
| `05-yayin-stratejisi.html` | Yayın stratejisi, hedef mecra, donanım doğrulaması |
| `06-olcum-birimi.html` | Ölçüm birimi, ADR-025 boru hattı eki |
| `index.html` | Kümenin kapak sayfası ve kendi karar takvimi |

> **NOTE · The cluster's own calendar is superseded on two rows.** `index.html` prints
> 16 Eylül for the first group and 30 Eylül for ADR-014. Both are superseded by this
> cover and by the `## Circulation, as-of 2026-09-14` section of the decisions register.
> The cluster is a dated document and is left unedited; where the two disagree, the
> register is authoritative.
