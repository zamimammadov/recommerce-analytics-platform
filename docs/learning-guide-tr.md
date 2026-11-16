# Adım Adım Öğrenme Rehberi

Bu rehberin amacı projeyi ezberletmek değil, her kararın nedenini anlamanı
sağlamaktır. Bir mülakatta kod satırını değil, çözmeye çalıştığın problemi ve
trade-off'u anlatabilmelisin.

## 1. Önce iş problemini tanımla

“Data pipeline yapacağım” bir iş problemi değildir. Bu projedeki problem:

> Operasyon ve ürün ekipleri günlük arz, engagement, dönüşüm, satış süresi ve
> satıcı performansı metriklerine güvenebilmelidir.

Örnek soru:

> Kaç ürün satıldı?

Bu soru tek başına belirsizdir. Sipariş oluşturulması mı, ödemenin alınması mı,
teslimatın tamamlanması mı? İptaller dahil mi? Biz önce tanımı yapar, sonra SQL
yazarız. Bu projede GMV, en son durumu `paid`, `shipped` veya `completed`
olan siparişlerin ürün fiyatını toplar ve kargoyu ayrı tutar.

### Senin kontrol sorun

Bir metrik için numerator, denominator, zaman penceresi ve grain'i
açıklayamıyorsan model henüz hazır değildir.

## 2. Grain kavramını öğren

Grain, tablodaki tek satırın neyi temsil ettiğidir.

- `events`: bir değişmez kullanıcı etkileşimi
- `orders`: bir siparişin teslim edilen bir versiyonu
- günlük KPI martı: bir tarih

Yanlış grain duplicate ve yanlış toplamlara yol açar. Bir sipariş altı kez
status değiştirdiyse, ham tabloda altı versiyon bulunabilir; “mevcut sipariş”
fact'inde yalnızca en güncel versiyon seçilmelidir.

## 3. Neden sentetik veri kullanıyoruz?

Gerçek şirket verisini paylaşmak hukuki, gizlilik ve mülkiyet riski taşır.
Sentetik üretici ile:

- aynı seed aynı veriyi üretir;
- bilinçli hatalar oluşturabiliriz;
- beklenen sonucu önceden biliriz;
- gerçek isim, e-posta ve kişisel veri kullanmayız.

Örnek: Seed `42` ile her çalışmada belirli bir listing'e negatif fiyat
eklenebilir. Test, bunun quarantine'e gitmesini doğrular.

Sentetik veri gerçek pazar davranışı kanıtı değildir. “Bu kategoride gerçek
satış arttı” diyemeyiz; yalnızca analiz yöntemini gösterebiliriz.

## 4. Incremental yükleme nedir?

Full refresh her çalışmada bütün geçmişi yeniden yükler. Incremental yükleme
yalnızca yeni veya değişmiş teslimatı işler.

Örnek:

```text
2026-11-01: 10.000 eski kayıt
2026-11-02:    500 yeni/değişmiş kayıt
```

Incremental pipeline ikinci gün 10.500 kaydı tekrar yazmak yerine 500 kaydı
işler. Ancak geçmiş bir dosya geç gelirse onu da seçerek backfill yapabilmelidir.

Bu projede incremental davranış ingestion katmanındadır. dbt fact ve mart
tabloları küçük demo ölçeğinde tam olarak yeniden oluşturulur. Bir katmanın
incremental olması bütün sistemin her katmanının incremental olduğu anlamına gelmez.

## 5. Idempotency neden önemlidir?

Bir pipeline hata verdiğinde operatör genellikle tekrar çalıştırır. Tekrar
çalıştırmak duplicate üretiyorsa sistem güvenli değildir.

Bu projede:

1. Dosyanın SHA-256 değeri alınır.
2. Başarıyla işlenen checksum kayıtlıysa dosya tekrar yüklenmez.
3. Stable record/version anahtarları ikinci savunma katmanıdır.
4. Dosya yükleme bir transaction içinde yapılır.

Örnek beklenen davranış:

```text
İlk çalıştırma:  2.000 valid + 3 rejected
İkinci çalışma:  0 yeni kayıt; completed checksum skipped
```

## 6. Validation ile data-quality testi farklıdır

Validation, tek kaydın sözleşmeye uygun olup olmadığını yüklemeden önce kontrol eder:

- fiyat negatif mi?
- zorunlu ID boş mu?
- status izin verilen listede mi?
- timestamp okunabiliyor mu?

Data-quality testi, yüklenmiş veri kümesinin bütünsel kuralını kontrol eder:

- her `seller_id` gerçekten users tablosunda var mı?
- güncel `order_id` değerleri unique mi?
- buyer ve seller farklı mı?
- parasal tutarlar geçerli mi?

İki katman da gereklidir.

Rejection oranı ve freshness için otomatik operasyonel eşikler yararlı ek
kontrollerdir; bu sürümde sürekli izlenen/routed alert üreten servis yoktur.

## 7. Quarantine neden silmekten iyidir?

Hatalı kaydı sessizce atarsan şu sorular cevapsız kalır:

- Kaç kayıt kayboldu?
- Hangi dosyadan geldi?
- Neden reddedildi?
- Upstream düzelttiğinde nasıl karşılaştıracağız?

Quarantine tablosu payload, sebep, dosya ve zamanı saklar. Fakat invalid veriyi
analitik tabloların içine sokmaz.

## 8. Raw, staging ve marts neden ayrıdır?

### Raw

Kaynağa yakın, lineage içeren kabul edilmiş versiyonlardır. İş KPI'sı burada hesaplanmaz.

### Staging

Tipler, kolon adları, deduplication ve temel standardizasyon yapılır.

### Dimension/fact

Entity ve olaylar açık grain ile modellenir.

### Mart

Sell-through, funnel veya seller performance gibi tekrar kullanılacak business
tanımları uygulanır.

Bu ayrım hatayı en erken sorumlu katmanda bulmayı kolaylaştırır.

## 9. SCD Type 2 neyi çözer?

Bir listing'in fiyatı €50'den €40'a düşsün. Overwrite yaparsak geçmişte fiyatın
€50 olduğunu kaybederiz.

```text
listing_id | price | valid_from | valid_to   | current
lst_101    | 50.00 | 2026-11-01 | 2026-11-05 | false
lst_101    | 40.00 | 2026-11-05 | null       | true
```

SCD2, gözlemlenen geçmiş versiyonlar saklandığında hem “şu anki fiyat nedir?”
hem de “3 Kasım'daki fiyat neydi?” sorusunu cevaplamaya yardımcı olur.
dbt snapshot bu versiyonları yönetir.

Bu cevap yalnız snapshot'ın gördüğü versiyonlar için mümkündür. İki tarih
arasındaki değişikliği hiç snapshot almadıysak o ara versiyon otomatik oluşmaz.
Bu nedenle demo her günlük delivery'den sonra snapshot çalıştırır. Ayrıca
fact/mart tabloları henüz geçmiş tarihli as-of dimension join kullanmaz;
güncel dimension ile ayrı snapshot geçmişini birbirinden ayırmalısın.

## 10. Late-arriving data ve backfill

Bir sipariş Pazartesi gerçekleşmiş, dosyası Perşembe gelmiş olabilir.

- `order_at`: Pazartesi, yani event time
- `ingested_at`: Perşembe, yani processing time

Perşembe günü Pazartesi partition'ını backfill eder, etkilenen martları yeniden
hesaplarız. `order_at` değerini Perşembe yapmayız; bu gerçeği saklamak olur.

Geç delivery Perşembe klasöründe olsa da `order_at` Pazartesi olabilir. Dosya
partition tarihi, olay tarihi ve yüklenme tarihi aynı kavram değildir. Bu
sürümde seçilen delivery yüklenir, ardından dbt modelleri full rebuild edilir.

## 11. Airflow'un görevi nedir?

Airflow business SQL yazma yeri değildir. Şunları yönetir:

- hangi görev hangisinden sonra çalışır;
- retry sayısı ve gecikmesi;
- logical date;
- geçmiş tarih backfill'i;
- task log ve durumları.

Aynı Python CLI Airflow olmadan da çalışır. Böylece orchestration ile business
logic birbirine kilitlenmez.

## 12. dbt'nin görevi nedir?

dbt warehouse içindeki dönüşümleri SQL olarak yönetir:

- source ve lineage
- staging dönüşümleri
- snapshot/SCD2
- fact/dimension/mart
- unique, not-null, relationship ve custom testler
- dokümantasyon

dbt dosya indirmez ve Airflow'un yerine genel workflow yönetmez.

## 13. Logging, audit ve monitoring farkı

- **Log:** ayrıntılı çalışma mesajı; örneğin bağlantı retry edildi.
- **Audit table:** yapısal run sonucu; başlangıç, bitiş, batch ve row count.
- **Metric/monitor:** zaman içinde izlenen sinyal; rejection ratio veya freshness.
- **Alert:** bir sinyal eşiği aşınca doğru kişiye gönderilen bildirim.

Bu sürümde structured log, audit ve persisted DQ sonuçları vardır. Merkezi
metric toplama, dış alert servisi ve otomatik alert yönlendirmesi henüz yoktur.

## 14. CI/CD neyi kanıtlar?

GitHub Actions her değişiklikte lint ve test çalıştırır. Böylece “benim
bilgisayarımda çalışıyor” yerine tekrar üretilebilir kontrol oluşur.

CI test ve build'dir. CD, başarılı artefact'ın bir ortama deploy edilmesidir.
Bu projenin local sürümünde CI workflow'u vardır; cloud CD uygulanmamıştır.
GitHub'a yükledikten sonra workflow'un gerçekten yeşil tamamlandığını ayrıca
kontrol et. Workflow dosyasının bulunması başarılı koşu kanıtı değildir.

## 15. Secrets yönetimi

Parolayı Python veya YAML dosyasına yazmayız:

```python
# yanlış
password = "postgres123"

# doğru yaklaşım
password = os.environ["POSTGRES_PASSWORD"]
```

`.env.example` sadece değişken isimlerini ve güvenli local örnekleri gösterir;
gerçek `.env` Git'e girmez. Cloud ortamında bunun yerini bir secrets manager ve
workload identity alır.

## 16. Neden Kafka ve Kubernetes yok?

Günlük CSV batch'i için Kafka kullanmak sahte karmaşıklıktır. Saniyelik latency
ihtiyacı ve sürekli event producer bulunmamaktadır.

Tek bilgisayardaki container'lar için Kubernetes de gereksizdir. Docker Compose
aynı ortamı tekrar kurmak için yeterlidir. Mülakatta önemli olan “hangi tool'u
biliyorum?” değil, “hangi şartta gerekli olur?” sorusunu cevaplamaktır.

## 17. Performans nasıl ele alınır?

Önce ölçer, sonra optimize ederiz:

1. Veri hacmini ve süreyi kaydet.
2. Yavaş sorguda `EXPLAIN (ANALYZE, BUFFERS)` incele.
3. Filtre/join pattern'ine göre index değerlendir.
4. Partition pruning veya incremental model ihtiyacını ölç.
5. Değişiklikten önce/sonra aynı benchmark'ı çalıştır.

Rastgele index veya milyonlarca yapay kayıt eklemek performans mühendisliği değildir.

## 18. Projeyi nasıl göstereceksin?

Demo sırası:

1. Business problemini açıkla.
2. Architecture diagramını göster.
3. Bir valid, bir invalid source row göster.
4. Pipeline'ı çalıştır ve audit/quarantine sayılarını göster.
5. Aynı komutu tekrar çalıştırarak idempotency kanıtla.
6. SCD2 fiyat geçmişini göster.
7. dbt test ve lineage'i göster.
8. Bir KPI martını business tanımıyla anlat.
9. Late-data backfill senaryosunu açıkla.
10. Neden Kafka/Kubernetes kullanmadığını anlat.

Tool listesinden önce problem ve sonuç konuşmak seni daha olgun gösterir.

## 19. Kendi kendine soracağın kontrol soruları

- Her tablonun grain'ini tek cümlede söyleyebiliyor muyum?
- Duplicate dosyada neden duplicate oluşmadığını gösterebiliyor muyum?
- Bir invalid kaydın yolculuğunu source'tan quarantine'e takip edebiliyor muyum?
- Bir geç kaydın hangi martları etkilediğini açıklayabiliyor muyum?
- Current state ile historical/as-of analizi ayırabiliyor muyum?
- Bir dbt testini neden seçtiğimi anlatabiliyor muyum?
- Projenin local simülasyon sınırlarını dürüstçe söyleyebiliyor muyum?

Hepsine cevap verebildiğinde projeyi yalnızca çalıştırmış değil, anlamış olursun.

## 20. Sonraki geliştirmeler

MVP bittikten sonra kanıt temelli sırayla:

1. Gerçek benchmark ve query plan analizi
2. Onaylı schema-evolution senaryosu
3. Local alert receiver veya OpenTelemetry/Prometheus gözlemi
4. Tek bir cloud'a Terraform deployment
5. Küçük A/B test veya güven aralığı analizi

Kafka ve Kubernetes yalnızca yeni requirement onları haklı çıkarırsa gelir.
