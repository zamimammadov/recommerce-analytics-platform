# Zamin için başlangıç ve sunum rehberi

Bu proje, sentetik bir ikinci el pazarındaki günlük veriyi güvenilir analitik
tablolara dönüştürüyor. Amaç, bir Junior Data/Analytics Engineer görüşmesinde
verinin kaynaktan sonuca nasıl geldiğini ve hatalar karşısında ne olduğunu
çalışan örneklerle anlatabilmen.

Kod AI desteğiyle geliştirildi. Bunu saklaman gerekmiyor. Sunarken kendi
deneyimini doğru ifade et: “AI destekli olarak geliştirdim; pipeline'ı
çalıştırdım, davranışını test ettim, tasarımı inceledim ve şu değişiklikleri
kendim uyguladım.” Bu cümleyi ancak ilgili çalışmaları yaptıktan sonra kullan.
Kodun tamamını tek başına yazdığını veya gerçek şirket sistemini production'da
yönettiğini söyleme.

## İlk beş adım

### 1. İş sorusunu ve metrikleri anla

Önce [business-case.md](business-case.md) dosyasını oku. Örneğin GMV, bu
projede durumu `paid`, `shipped` veya `completed` olan siparişlerin ürün
değeridir. Kargo hariçtir ve şirket geliri değildir.

Kendine sor: €30 ürün + €5 kargo ve iptal edilmiş €20 sipariş varsa GMV
kaçtır? Bu tanıma göre €30. `created` durumundaki sipariş de GMV'ye girmez.

### 2. Dört kaynağın tek satırını açıkla

[data-model.md](data-model.md) üzerinden `users`, `listings`, `events` ve
`orders` tablolarının grain'ini öğren. `listing_id` ürün ilanını,
`order_id` siparişi temsil eder. Bir siparişin birden çok source versiyonu
olabilir; güncel order fact'inde en yeni versiyonu seçiyoruz.

Kendine sor: sipariş önce `paid`, sonra `completed` gelirse iki satış mı var?
Hayır, aynı siparişin iki versiyonu var.

### 3. Demoyu çalıştır, üç kanıtı incele

```bash
cp .env.example .env
make demo
```

Demo iki günlük delivery'yi ayrı işler ve her gün snapshot alır. Şunları bul:

1. Negatif fiyatlı bir satır ve quarantine'daki hata nedeni.
2. Tekrar oynatmada sıfır yeni kayıt ve atlanan checksum'lar.
3. Fiyatı değişen aynı listing için kapanmış eski snapshot ve güncel versiyon.

Bu üç kanıtı doğrudan sorgulayan hazır örnekler
[`analysis/inspect_pipeline.sql`](../analysis/inspect_pipeline.sql) içinde.

Komutları anlamak için [runbook.md](runbook.md) ve `make help` kullan.
`make reset` veritabanı volume'unu siler; normal tekrar denemede gerekmez.

Çalışma makinesinin Docker disk sınırı nedeniyle tüm container demosu burada
tamamlanamadı. Python/dbt'yi bilgisayarda, PostgreSQL'i Docker'da çalıştıran
alternatif ise geçti. Gerçek test sonuçları ve bu alternatifin komutları
[verification.md](verification.md) içinde. Airflow'un bu sürümde yalnız
statik kontrol edildiğini sunumunda açıkça söyle.

### 4. Küçük bir değişikliği kendin yap

Önce var olan testleri oku: `NaN` fiyat, timezone'suz timestamp veya
buyer=seller sipariş nasıl ele alınıyor? Kapsanmayan bir sınır durumu seçip
kendi testini ekle ve hangi hatayı yakaladığını açıkla. Sonra
bir kategori için GMV ve completed order sorgusunu kendin yaz.

Çalıştırılacak kontroller:

```bash
make test
make lint
```

Bir testin fail olması her zaman testin yanlış olduğunu göstermez; önce
iş kuralını ve verinin hangi katmanda bozulduğunu incele.

### 5. Beş dakikalık demo hazırla

Sıra: iş problemi → veri modeli → pipeline → quarantine → replay → SCD2
geçmişi → bir metrik → mimari trade-off. [interview-guide.md](interview-guide.md)
örnek soruları içeriyor. [learning-guide-tr.md](learning-guide-tr.md) her
kavramı daha ayrıntılı örneklerle açıklıyor.

## Sunmadan önce cevaplayabilmen gerekenler

- Dosya hash'i ile satır/business key kontrolü farklı olarak neyi koruyor?
- Başarısız dosya yüklemesi ve tüm batch'in transaction sınırı nedir?
- Geç gelen satışta event time ile ingestion time neden farklı kalmalı?
- Neden ingestion incremental iken dbt modelleri full rebuild yapıyor?
- Snapshot'ın kaçırdığı ara versiyonu neden yalnız yeniden çalıştırarak geri getiremiyoruz?
- Fact tabloları neden bugün current dimension kullanıyor; as-of join eklesek ne değişir?
- GMV, AOV, order count ve sell-through'un pay/payda tanımı nedir?
- Listing stage flag'leri neden sıralı kullanıcı dönüşüm hunisi sayılmaz?
- Kafka veya Kubernetes hangi yeni ihtiyacı karşılayacak olursa eklenmeli?
- Bu projede henüz cloud deployment ve dış bildirimli monitoring neden yok?

## Kaç proje yapmalısın?

Eğitim ve staj deneyiminin yanına hedef iki iyi tamamlanmış public proje olsun:

1. Bu kapsamlı veri platformu: SQL, Python, modelleme, veri kalitesi ve operasyon.
2. Daha küçük product analytics/deney analizi: SQL + pandas + istatistik,
   açık metrik tanımı ve yazılı iş yorumu.

İkinci proje birincinin kopyası olmasın. Üçüncü projeyi ancak gerçekten farklı
bir yetkinliği kanıtlayacaksa ekle. Başvuruyu proje sayısı için geciktirme;
anladığın ve çalışan bir projeyle başlamak daha değerlidir. Kabul kararı ayrıca
CV, role uygunluk, SQL/Python görevi ve mülakat performansına bağlıdır.
