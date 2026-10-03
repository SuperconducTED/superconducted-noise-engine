# Üç motor ve derin model · Dr. Akba için özet (2026-10-04)

5 Ekim haftasındaki planlama görüşmesi için hazırlandı. Ayrıntılı plan İngilizce olarak
`docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` dosyasında. Bu sayfa onun
kısa Türkçe özeti. Takip eden issue: #110.

> **NOT · Sayılar hakkında.** Buradaki arşiv gözlemleri **geçicidir**. Bunlar, planlama
> sırasında `calibration-data` `43607a2` üzerinde 60 dosyaya bakılarak yapıldı. Kayıtlı
> ölçümler planın T1 ve T2 görevleriyle gelecek.

## 1. Sizden anladığımız

- Üç motor modu: Tip-1 bulanık, Aralık Tip-2 bulanık ve bir derin öğrenme modeli.
- Önce elimizde kaç parametre ve öznitelik olduğunu sayıyoruz. Özniteliklerin
  kombinasyonlarıyla kaç senaryonun oluşabileceğini çıkarıyoruz. Derin modeli buna göre
  çalıştırıyoruz.
- Sonra hangi özniteliklerin önemli olduğunu buluyor, öznitelik mühendisliği yapıyor ve
  modeli bunun üstüne ikinci katman olarak kuruyoruz.
- Model mimarisi ekip lideri olarak Mert'te.

## 2. Mimari kararlar (Mert, 2026-10-04)

| # | Karar |
| --- | --- |
| A1 | **İki aşamalı derin model.** 1. aşama tüm aday öznitelikle eğitilir ve onları sıralar. 2. aşama, yani üçüncü motor, seçilmiş ve mühendislikten geçmiş öznitelikle eğitilir. T1 ve IT2 kendi girdilerini korur. |
| A2 | **"Permütasyon" iki adımdır:** önce senaryo sayımı (her özniteliği düşük/orta/yüksek seviyeye ayırıp kombinasyonları ve arşivin bunlardan kaçını içerdiğini saymak), sonra eğitilmiş 1. aşama modelde permütasyon önemi. |
| A3 | **Örnek birimi, aşamalı.** Önce anlık görüntü başına bir satır (bugünkü bulanık motorlarla karşılaştırılabilir), sonra kübit başına bir satır. |
| A4 | **Elle yazılmış NumPy.** Yeni bağımlılık yok; ADR-005'in ruhu içinde. |
| A5 | **Belirsizlik bandı bölünmüş konformal tahminle.** Karşılaştırmanın birincil ölçütü band. |
| A6 | **Gelecek çalışma:** 1. aşamanın sıralaması üç motorun da girdisini seçebilir; bir de yığılmış nöro-bulanık model. |

## 3. Elimizdeki öznitelikler (geçici gözlem)

- Kübit başına, zamanla değişen ve tüm arşiv boyunca bulunan 6 öznitelik var: `T1`, `T2`,
  `readout_error`, `prob_meas0_prep1`, `prob_meas1_prep0` ve tek kübit kapı hatası
  (`sx`).
- `id`, `rx`, `x` ve `xslow` hataları her kübitte `sx` ile aynı; `measure` hatası
  `readout_error` ile aynı. Yani beş ad tek bir sayı.
- `init_error` 4 Ağustos'tan, `measure_2` 13 Ağustos'tan, `measure_reset` alanları 3
  Eylül'den beri var. Bunlar için bir eksik veri kuralı gerekiyor.
- Kenar başına `cz` ve `rzz` hataları ile `zz` terimleri de zamanla değişiyor.
- Bugünkü motor bunlardan 3 tanesini kullanıyor: `T1`, `T2` ve `readout_error`'ın
  kübitler üzerinden ortalaması.

**Senaryo sayısı neden önemli:** her özniteliği 3 seviyeye ayırırsak `n` öznitelik
`3^n` hücre verir. Bu, ızgara bir bulanık motorun ihtiyaç duyacağı kural sayısıyla aynı.
6 öznitelik 729 hücre ve 729 kural demek; bu da yaklaşık 10.200 sonuç parametresi ve
yaklaşık 51.000 durumluk bir taban eder. Arşivde ise 740 farklı durum var (`43607a2`,
geçici). Bulanık motorlar tüm öznitelikleri alamaz. Arşivin bu hücrelerden kaçını
gerçekten doldurduğu T2 göreviyle ölçülecek.

## 4. Sizin vereceğiniz kararlar

1. Önem ölçümü için tekli ve gruplu permütasyon önemi sizin kastettiğiniz yöntem mi?
2. Bandların karşılaştırması: üç motoru da konformal ile mi kalibre edelim, yoksa üçünü
   de ham haliyle karşılaştırıp kapsamayı mı raporlayalım? IT2'nin Karnik-Mendel bandı
   konformal değil; birini kalibre edip diğerini etmezsek karşılaştırma kısmen yöntemi
   ölçer.
3. Derin model makalenin iddiasında eşit bir motor mu, yoksa tezin geçmesi gereken taban
   mı?
4. Kübit başına aşama (aşama B) bu makalenin içinde mi, gelecek çalışma mı?
5. Kısmi geçmişli alanlar için eksik veri kuralı: atlamak mı, bulanık maksimum entropi mi
   (2026-05-25 sorularından Q5)?
6. Gelecek çalışma önerileri (A6) makalede anılmaya değer mi?
