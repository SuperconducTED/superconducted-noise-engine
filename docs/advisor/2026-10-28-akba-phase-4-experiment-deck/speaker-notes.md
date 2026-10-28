# Konuşmacı notları / Speaker notes

Sunum: 2026-10-28, Dr. Fırat Akba için faz 4 ara sunumu. Her slayt için kısa bir Türkçe
paragraf; İngilizce ikizinin notu kapalı bir blokta. Notlar her slaydın `<aside>` öğesinden
alındı, yani slaytlardaki notlarla birebir aynıdır.

## 1. Cihaz Son Okumayı mı, Seviyeyi mi İzliyor?

Zaman ayırdığınız için teşekkür ederim. Bu sunum faz 4 donanım deneyini, yani #125’i, neden yaptığımızdan sizden ne istediğimize kadar anlatıyor. Gösterilen her şey bugün sunulanın kaydıdır; içindeki hiçbir şey sizin onayınız olarak kaydedilmez.

<details>
<summary>English: Does the Device Follow the Reading or the Level?</summary>

Thank you for your time. This deck explains the phase-4 hardware experiment, issue #125, from the reason we run it to what we ask of you. Everything shown is a record of what was presented today; nothing in it is recorded as your approval.

</details>

## 2. Mühendisler Sadakat Hedefini Tutturamıyor

Proje pratik bir nedenle var; lider bunu 2026-10-23’te yazdı: tasarımlarını fiziksel devreye dönüştüren mühendisler sadakat hedefini tutturamıyor ve son okumadan kurulan hazır gürültü modeli onları uyarmıyor. Motorun işi, koşudan önce hangi kübitlerin kullanılacağını ve hangi sadakatin bekleneceğini dürüst bir aralıkla söylemek. Sunumun geri kalanı, bu tahminin neye merkezlenmesi gerektiğine karar verecek tek deney hakkında.

<details>
<summary>English: Engineers Miss Their Fidelity Target</summary>

The project exists for a practical reason the lead stated on 2026-10-23: engineers turning designs into physical circuits miss their fidelity target, and the stock noise model built from the latest reading does not warn them. The engine’s job is to predict, before the run, which qubits to use and what fidelity to expect, with an honest range. The rest of the deck is about the one experiment that decides what that prediction should be centred on.

</details>

## 3. Seviye, Son Okumayı Yener

Arşivden dört olgu; 2026-10-23’te ölçüldü ve hâlâ geçici. Bir kübitin kalibrasyonu bir seviye etrafında yavaşça hareket ediyor, üstünde bağımsız bir saçılma var. Basit bir kayan bant, her bandın geçmesi gereken çıta. Bir haftalık kübit başına model, çipi tekdüze sayan taze modeli yeniyor. Grafikte de seviyeye dayalı bütün yöntemler kayan bandın yanında duruyor; son okuma, yani persistence, çok daha kötü.

<details>
<summary>English: The Level Beats the Latest Reading</summary>

Four facts from the archive, measured on 2026-10-23 and still provisional. A qubit’s calibration moves slowly around a level with independent scatter on top. A simple rolling band is the bar any band has to beat. A per-qubit model a week old beats a fresh model that treats the chip as uniform. And on the chart: every level-based method sits near the rolling band, while the latest reading, persistence, is far worse.

</details>

## 4. Kalibrasyonlar arasında cihaz son okumayı mı, seviyeyi mi izliyor?

Deneyin tamamı tek cümlede. Arşiv bir seviye etrafında dağılmış okumalar gösteriyor ama saçılmanın ne olduğunu söyleyemiyor. Ölçüm gürültüsüyse doğru olan seviyedir ve ürün seviyeye dayalı bir modeldir. Gerçek bir dalgalanmaysa dürüst ürün aralıktır. Bunu yalnızca kalibrasyonlar arasında ölçülen cihaz yanıtlayabilir.

<details>
<summary>English: Between calibrations, does the device follow the latest reading, or the level?</summary>

This is the whole experiment in one sentence. The archive shows readings scattered around a level, but it cannot say what the scatter is. If it is measurement noise, the level is the truth and the product is a level-based model. If it is real fluctuation, the honest product is the range. Only the device, measured between calibrations, can answer that.

</details>

## 5. Neler Var, Ne Hâlâ Açık

En yakın komşu QuBound: kalibrasyondan türetilmiş sınırlar yayımlıyor, ama sabit tek bir devre için ve çıktısı bir simülatöre yüklenemiyor. Kurniawan ve arkadaşları yerleşim seçiminde geçmiş kalibrasyonu son okumadan daha sağlam buldu; bu, derleme tarafında bizi destekliyor. Tahminin kendisini kimse test etmedi. Bulanık harita bir birleşim olarak yeni. Bizim zayıf noktamız, kanalın bugün çip genelinde tekdüze olması; kuantum dergisi için bu değişmek zorunda.

<details>
<summary>English: What Exists, and What Is Still Open</summary>

QuBound is the closest neighbour: it publishes calibration-derived bounds, but for one fixed circuit, and nothing it outputs loads into a simulator. Kurniawan and colleagues found historical calibration more robust than the latest reading for choosing a layout, which corroborates us on the compilation side. Nobody has tested the prediction itself. The fuzzy map is novel as a combination. Our own weakness is that the channel is chip-uniform today, and that has to change for a quantum venue.

</details>

## 6. S1: Son Okumayı Değil, Seviyeyi Taşı

Kural, tasarımın §7’sinin üç sonuca indirgenmiş halidir; esas olan tam metindir. Ön kayıt onu değiştirmeden tutar ve Bengisu’nun istatistik incelemesinden sonra, ilk işten önce dondurur. Kilit nokta şu: gönderim anındaki okumayı yenmek yetmez, çünkü bu kuyruktaki bayatlama olabilir. Seviye, iş gerçekten çalıştığı anda alınan okumayı yenerse S1 geçer; yenemezse ürün aralıktır ve makale, bu koşuyu donanım bölümü olarak taşıyan bulanık sistemler makalesidir.

<details>
<summary>English: S1: Carry the Level, Not the Latest Reading</summary>

The rule is the design’s §7, condensed into its three outcomes; the full wording governs. The pre-registration keeps it unchanged and freezes it before the first job, after Bengisu’s statistics review. The key point: beating the submission-time reading is not enough, because that could be staleness in the queue. If the level beats the reading taken when the job actually runs, S1 passes; if it does not, the range is the product and the paper is the fuzzy-systems one with this run as its hardware section.

</details>

## 7. Arm A: Bozunum Devreleri

Arm A, okuma ile seviyenin en doğrudan anlaşamadığı niceliği ölçer: bir gecikmeden sonra uyarılmış durumun ne kadarının hayatta kaldığı. Her öngörücü motorun kendi kanalından bir tahmin verir, donanım da ölçülen değeri. İkisinin en çok ayrıştığı sekiz kübit, dördü seviyenin altında, dördü üstünde; bir de hiçbir okumaya bakılmadan seçilmiş dört kontrol. Ayırt edici satırlar yapısı gereği seviyeyi kayırır, bu yüzden kontrollerden hep ayrı raporlanır.

<details>
<summary>English: Arm A: Decay Circuits</summary>

Arm A measures the quantity the reading and the level disagree about most directly: how much of the excited state survives after a delay. Each predictor gives a predicted survival through the engine’s own channel, and the hardware gives the measured one. Eight qubits where the two disagree most, four below and four above the level, and four controls chosen without looking at any reading. The discriminating rows favour the level by construction, so they are always reported apart from the controls.

</details>

## 8. Arm B: Mühendisin Yerleşim Sorusu

Arm B mühendisin sorusunu doğrudan sorar: küçük bir devre için hangi yerleşim en iyi ölçülecek? Her öngörücü altı aday yerleşimi sıralar, donanım altısını da ölçer ve sıralamayı puanlarız. Bekleme bloğu, her yerleşimin koherensini önemli kılan şeydir. İki kübitlik kapı hatası her öngörücü için aynı son okumadır; bu yüzden seviyenin burada kazandığı, tamamen seviyeye dayalı bir modelin kazancını olduğundan az gösterir.

<details>
<summary>English: Arm B: the Engineer’s Layout Question</summary>

Arm B asks the engineer’s question directly: for one small circuit, which layout will measure best? Each predictor ranks six candidate layouts, the hardware measures all six, and we score the ranking. The idle block is what makes each layout’s coherence matter. The two-qubit gate error is the same latest reading for every predictor, so whatever the level gains here understates a fully level-based model.

</details>

## 9. Hangi Kübitler, Neden

Liderin 2026-10-24’te kabul ettiği dört öneriden üçü hangi kübitleri ölçtüğümüze karar veriyor. Akışı soldan sağa okuyun. Pencere tabanı: seviye gerçekten bir ortalama olsun, ileri taşınan tek bir değer olmasın. Önce kontroller: o günün okumalarına bağlı olamasınlar. İşaret dengesi: çoğu gün en büyük ayrışmaların hepsi düşüş; tek taraflı bir test soruyu yalnızca düşüşler için yanıtlar.

<details>
<summary>English: Which Qubits, and Why</summary>

Three of the four proposals the lead accepted on 2026-10-24 decide which qubits we measure. Read the funnel left to right. A window floor, so that a level really is an average and not one value carried forward. Controls frozen first, so they cannot depend on the day’s readings. And sign balance, because on most days the largest disagreements are all dips, and a one-sided test would only answer the question for dips.

</details>

## 10. Kazananı Izgara Seçmemeli

Bu bir sürprizdi. PR #126’nın kaydı, tasarımın ızgarasının seviyeyi kayırdığını söylüyordu. Hesaplanınca okumayı kayırdığı çıktı, hem de iki tarafta; çünkü ızgaranın merkezlendiği tahmin eğrinin en dik yerine düşüyor ve aynı hata için en çok bedeli ödüyor. Resimdeki teal ve turuncu ızgaraların birleşimi bu yanlılığı kaldırıyor; bütçe kısıt olmadığı için üç ek gecikme her öngörücüye en duyarlı noktalarını kazandırıyor.

<details>
<summary>English: The Grid Must Not Pick the Winner</summary>

This was a surprise. PR #126’s record said the design’s grid favoured the level. Computed, it favours the reading, on both sides, because the prediction the grid is centred on sits on the steepest part of the curve and pays the most for the same error. The union of both grids, teal and orange in the picture, removes that bias, and with the budget not a constraint the three extra delays buy each predictor its own most sensitive points.

</details>

## 11. 14 Gün, Günde Bir İş, 03:45 UTC (İstanbul 06:45)

On dört iş, günde bir, sabit bir saatte. İş şeridinin altındaki çubuk bir UTC günü: çip genelindeki yeniden kalibrasyonların çoğu akşam geliyor; 03:45 UTC’deki gönderim onlardan epey uzakta ve liderin izin verdiği yedi saatin en iyisi. Bu, IBM’in mayıs-ekim takviminin bir özelliği ve kayabilir. Dördüncü öngörücü, yürütme anındaki okuma, gürültüyü bayatlamadan ayırabilmemiz için orada.

<details>
<summary>English: 14 Daily Jobs at 03:45 UTC (06:45 Istanbul)</summary>

Fourteen jobs, one a day, at a fixed hour. The bar below the job strip is one UTC day: most chip-wide recalibrations land in the evening, and the submission at 03:45 UTC sits well clear of them, the best of the seven hours the lead allowed. That is a property of IBM’s schedule from May to October and may move. The fourth predictor, the reading at execution time, is there so that we can tell noise from staleness.

</details>

## 12. Sabitlenmiş Tek Arşiv, Çapraz Kontrollü

Boru hattını soldan sağa okuyun. IBM kalibrasyon özelliklerini yayımlıyor; yoklayıcımız saatte bir anlık görüntüyü ayrı bir dalda saklıyor; dosyaları değil farklı cihaz durumlarını sayıyoruz, çünkü pek çok sorgu aynı durumu tekrar ediyor; her analiz arşiv commit’ini sabitliyor ve önce durum indeksini kontrol ediyor. Otuz dakikada bir sorgulanan kamuya açık bir arşiv her eğitim alanında bizimkiyle değer değer örtüşüyor, arşivi ocağa kadar geriye uzatıyor ve saatlik sorgumuzun kaçırdığı durumları yakalıyor. Benimsenmesi taslak bir karar, ADR-029; henüz verilmedi.

<details>
<summary>English: One Pinned Archive, Cross-Checked</summary>

Read the pipeline left to right. IBM publishes calibration properties; our poller stores one snapshot an hour on a dedicated branch; we count distinct device states, not files, because many polls repeat the same state; every analysis pins the archive commit and first checks the state index. A public archive polled every thirty minutes agrees with ours value for value on every training field, extends it back to January and catches states our hourly poll missed. Adopting it is a draft decision, ADR-029, not yet taken.

</details>

## 13. Deneyin Arkasındaki Sekiz Sayı

Veri sekiz sayıda, her biri register satırıyla. Üst sıra seviye artı saçılma resmi: artışlar bir seviye etrafında saf saçılma gibi davranıyor, bir sonraki değişimi son okuma değil seviye açıklıyor, saçılma yaklaşık üçte bir log birimi genişliğinde ve parametresiz kayan bant uydurulmuş bandı yeniyor. Alt sıra testin tasarımının dayandığı şeyler: bir haftalık kübit başına değer taze tekdüzeyi yeniyor, hemen her kübitin penceresinde günde yaklaşık bir T1 değeri var, taramalar yaklaşık günlük geliyor ve hepsi tek bir sabitlenmiş arşiv durumunda. Her sayı, Burak’ın masaüstü yeniden üretene kadar geçici.

<details>
<summary>English: Eight Numbers Behind the Experiment</summary>

The data in eight numbers, each with its register row. The top row is the level-plus-scatter picture: increments behave like pure scatter around a level, the level explains the next change while the latest reading explains none, the scatter is about a third of a log unit wide, and a parameter-free rolling band beats a fitted one. The bottom row is what the test design rests on: a week-old per-qubit value beats a fresh uniform one, almost every qubit has about one T1 value a day in its window, sweeps come about daily, and all of this is at one pinned archive state. Every number is provisional until Burak’s desktop reproduces it.

</details>

## 14. Donanım Sayısından Önce Sabit İstatistik

İstatistik, hiçbir donanım sayısı yokken sabitleniyor. Bengisu’nun örüntü dedektörü incelemesinden iki ders önceden uygulanıyor: etiketler eğitim sınırının ötesine uzanmamalı ve bootstrap bütün takvim günü bloklarını yeniden örneklemeli. Her eşiğin önce null değeri hesaplanıyor; böylece bilgisi olmayan bir öngörücünün ne puan alacağını biliyoruz. Yeniden örnekleme biriminin kendisi hâlâ onun incelemesinde.

<details>
<summary>English: Statistics Fixed Before Any Hardware Number</summary>

The statistics are fixed before any hardware number exists. Two lessons from Bengisu’s review of the pattern detector are applied in advance: labels must not reach across the training boundary, and the bootstrap must resample whole blocks of calendar days. Every threshold gets its null value first, so we know what a predictor with no information would score. The resampling unit itself is still in her review.

</details>

## 15. Örüntü Dedektörü, Tek Slaytta

Öneriniz dürüstçe, önce protokol yazılarak test edildi. Kaydedildiği haliyle lojistik model geçiyor. Ama inceleme, geçtiği null’ın kötü kalibre olduğunu gösterdi; basit bir sabite karşı kazanç küçük ve önceden belirlediğimiz eşiğin altında. Benimsediğimiz sonuç Bengisu’nunki: bu, ne kullanışlı bir fiziksel örüntü ne de bir sinir ağı modeline ihtiyaç gösteriyor. Ağ, ancak bir sonraki görülmemiş değerlendirme daha güçlü kuralı geçerse çalışacak; o kuralın onay talebi ayrı bir not.

<details>
<summary>English: The Pattern Detector, in One Slide</summary>

Your suggestion was tested honestly, with the protocol written first. As registered, the logistic model passes. But the reviewer showed that the null it passed was badly calibrated, and against a simple constant the gain is small, below the margin we set in advance. Bengisu’s conclusion is the one we adopt: this does not show a useful physical pattern, and it does not show a need for a neural model. The network runs only if the next unseen evaluation clears the stronger rule; the request to ratify that rule is a separate brief.

</details>

## 16. Önce Protokol, Sonra Sayılar, En Son Masaüstü

Yeniden üretilebilirlik iş sırasının içine yerleşik; zinciri soldan sağa okuyun. Protokol betik çalışmadan önce commit ediliyor, ön kayıt ilk işten önce donduruluyor, her girdi bir commit’e sabitleniyor ve her arşiv betiği önce aynı arşivi gördüğünü kanıtlıyor. Örüntü dedektörünün dokuz değişikliği bir zayıflık değil: her biri değiştirdiği koşudan önce tarihlendi. Her sayının son sözü Burak’ın masaüstü yeniden üretimi.

<details>
<summary>English: Protocol First, Numbers Second, Desktop Last</summary>

Reproducibility is built into the order of work; read the chain left to right. The protocol is committed before the script runs, the pre-registration is frozen before the first job, every input is pinned to a commit, and every archive script first proves it sees the same archive. The nine amendments of the pattern detector are not a weakness: each was dated before the run it changed. The final word on every number is Burak’s desktop reproduction.

</details>

## 17. Yapım Sırası, Tarihler Hedef Olarak

Liderin 2026-10-28’de belirlediği sıra, bir zaman çizelgesi olarak. Donanım testi kritik yol: önümüzdeki iki haftada çevrimdışı yarı, dondurma ve ilk iş; sonra günlük işler ve karar kuralı. Kübit başına kanal, ilk iş raporlandığında açılıyor. Bulanık sistem ve makale baştan sona yürüyor; makale taslağı, donanım ne derse desin L4 kapısında başlıyor. Sinir ağı modeli aralıkta yeni veriyi bekliyor. Tarihler hedef, söz değil.

<details>
<summary>English: Build Order, With Dates as Targets</summary>

The order the lead set on 2026-10-28, drawn as a timeline. The hardware test is the critical path: the offline half, the freeze and the first job in the next two weeks, then the daily jobs and the decision rule. The per-qubit channel opens when the first job reports. The fuzzy system and the paper run all along, and the paper’s draft starts at gate L4 whatever the hardware says. The neural model waits for new data in December. The dates are targets, not promises.

</details>

## 18. Makale Neyi İddia Edebilir, Neyi Edemez

Makale için önerdiğimiz sınır bu. Arşiv sonuçları güçlü, ama cihaz hakkında değil, raporlanan kalibrasyon tahminlerinin kalıcılığı hakkında. Onları cihaz hakkında bir iddiaya dönüştüren şey donanım testi. Kuantum dergisi ancak S1 geçerse açık; bulanık sistemler makalesi her durumda var, bu koşu da onun donanım bölümü.

<details>
<summary>English: What the Paper Can and Cannot Claim</summary>

This is the boundary we propose for the paper. The archive results are strong, but they are about the persistence of reported calibration estimates, not about the device. The hardware test is what turns them into a claim about the device. A quantum venue is open only if S1 passes; the fuzzy-systems paper exists either way, with this run as its hardware section.

</details>

## 19. Yalnızca Sizin Yanıtlayabileceğiniz Üç Soru

Yalnızca kendimizin yanıtlayamayacağı şeyleri soruyoruz. Hangi dergiler, hangi sırayla. O dergideki hakemler donanım üzerinde ön kayıtlı bir geçti/kaldı kuralı bekler mi. Ve iddialar nerede durmalı. Ölçebildiğimiz her şeyi kendimiz ölçüyoruz. Bugün söyledikleriniz danışman kaydına sizin sözleriniz olarak geçer; bu sunum yalnızca neyin gösterildiğini kaydeder.

<details>
<summary>English: Three Questions Only You Can Answer</summary>

We only ask what we cannot answer ourselves. Which journals, and in which order. Whether reviewers at that venue expect a pre-registered pass or fail rule on hardware. And where the claims should stop. Anything we can measure, we measure. Whatever you say today is recorded in the advisor register as your words; this deck records only that it was shown.

</details>

## 20. Her Sayı Bir Satıra Dayanır

Bu slaytlardaki her sayı bu register satırlarından birine dayanıyor. Soldaki tablo main’de; sağdaki, ön kayıt dalı yeniden kurulup incelenene kadar yalnızca o dalda. Ölçülen her satır, adı verilen arşiv commit’inde tarihli bir çapadır, güncel bir değer değildir; Burak’ın masaüstü yeniden üretene kadar da geçicidir.

<details>
<summary>English: Every Number Traces to a Row</summary>

Every number on these slides traces to one of these register rows. The left table is on main; the right one lives only on the pre-registration branch until that branch is rebuilt and reviewed. Each measured row is a dated anchor at the archive commit named, not a current value, and each is provisional until Burak’s desktop reproduces it.

</details>
