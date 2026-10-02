# Input Schema — MalikAxiom Lead AI (Standardized Schema)

This file documents the standardized 22-column CSV input schema and scraper mapping accepted by the pipeline.

## Standardized 22 Columns (In Exact Order)

```text
business_name,phone,website_phones,email,website,facebook,instagram,linkedin,twitter,whatsapp,youtube,tiktok,address,category,rating,reviews,hours,latitude,longitude,place_id,cid,google_maps_url
```

## Normalizing Raw Scraper CSVs

If you have raw Google Maps scraper exports (e.g. with 36 columns such as `title`, `link`, `open_hours`, `review_rating`, `review_count`, `complete_address`, `emails`, etc.), you can normalize them into the clean 22-column format using:

```bash
cd malik-lead-ai
python3 main.py normalize input/part00.csv -o input/part00_standardized.csv
```

Or execute pipeline directly (auto-detects and maps all column variants):

```bash
python3 main.py pipeline input/part00.csv
```

## Column Mapping Table

| Standard Field | Accepted Column Name Variants |
|----------------|-------------------------------|
| `business_name` | `business_name`, `title`, `business`, `name`, `company`, `store_name`, `shop_name` |
| `phone` | `phone`, `phone_number`, `contact`, `telephone`, `gen_phone`, `google phones`, `google_phones`, `phones` |
| `website_phones` | `website_phones`, `website phones`, `web_phone`, `web_phones` |
| `email` | `email`, `emails`, `email_address`, `contact_email`, `mail`, `email_addresses` |
| `website` | `website`, `site`, `url`, `website_url`, `web_url` |
| `facebook` | `facebook`, `facebook_url`, `fb`, `fb_url`, `facebook_link` |
| `instagram` | `instagram`, `instagram_url`, `instagram_handle`, `ig`, `instagram_link` |
| `linkedin` | `linkedin`, `linkedin_url`, `linkedin_page`, `linkedin_link` |
| `twitter` | `twitter`, `twitter_url`, `x`, `x_url`, `twitter_handle` |
| `whatsapp` | `whatsapp`, `wa`, `whatsapp_number`, `whatsapp_phone`, `wa_number` |
| `youtube` | `youtube`, `youtube_url`, `youtube_channel`, `yt`, `youtube_page`, `youtube_link` |
| `tiktok` | `tiktok`, `tiktok_url`, `tiktok_handle`, `tiktok_link` |
| `address` | `complete_address`, `address`, `location`, `city`, `town`, `street_address`, `plus_code` |
| `category` | `category`, `business_category`, `type`, `categories`, `industry` |
| `rating` | `review_rating`, `rating`, `google_rating`, `stars`, `star_rating` |
| `reviews` | `review_count`, `reviews`, `google_reviews`, `reviews_count`, `total_reviews` |
| `hours` | `open_hours`, `hours`, `popular_times`, `operating_hours`, `business_hours`, `timezone` |
| `latitude` | `latitude`, `lat` |
| `longitude` | `longitude`, `lng`, `long`, `lon` |
| `place_id` | `place_id`, `data_id` |
| `cid` | `cid`, `input_id` |
| `google_maps_url` | `link`, `google_maps_url`, `maps_url`, `maps`, `maps url`, `google maps url`, `street_view_url`, `reviews_link` |

## Notes

- Original raw scraper columns are also preserved in research records (`original_source_data`).
- The pipeline seamlessly processes both pre-standardized 22-column CSVs and raw scraper export files.
