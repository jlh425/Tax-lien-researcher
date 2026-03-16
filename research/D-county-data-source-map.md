# Section D — County & State Data Source Map
**Created:** 2026-03-16
**Status:** V1.0 — Core lien and deed states mapped. Expand as new counties are targeted.

This document is the Discovery Agent's built-in reference for where to find data in each state and county. It is read at runtime when a user selects a target location.

---

## D.1 — US State Classification Table (All 50 States)

| State | Instrument | Primary Auction Platform | State-Level Bulk Data | Cert Rate Cap | Post-Sale Redemption | Notes |
|-------|-----------|--------------------------|----------------------|---------------|---------------------|-------|
| AL | Tax Deed | County-direct / courthouse | No | — | None | Sold to highest bidder; title may have clouds |
| AK | Tax Foreclosure | Borough-direct | No | — | None | Low volume; borough-level (not county) |
| AZ | **Lien Cert** | RealAuction (county subdomains) | No | 16% | — | Bidding starts at 16%, bid down; Feb auction statewide |
| AR | Tax Deed | County-direct / courthouse | No | — | None | Commissioner's deeds; annual sale |
| CA | Tax Deed | County-direct / auction.com (some) | Varies by county | — | None | No right of redemption post-sale; counties manage independently |
| CO | **Lien Cert** | RealAuction (county subdomains) | No | 15% | — | Rate set by State Bank Commissioner annually; Oct-Nov auction |
| CT | **Lien Cert** | Municipality-direct | No | 18% | — | Municipality-level (not county) |
| DE | Tax Deed | County-direct / Sheriff | No | — | None | Very low volume |
| FL | **Lien Cert** | LienHub / RealAuction (county-level) | State list published by FL DOR | 18% | — | Mandatory annual cert sale by June 1 (FS 197.402); 2yr to apply for deed |
| GA | Tax Deed | County-direct / Bid4Assets (some) | No | — | 12 months (homestead) / 0 others | Tax deed conveys good title after 1yr redemption period |
| HI | Tax Deed | State-direct | No | — | None | Very low volume; state-administered |
| ID | Tax Deed | County-direct | No | — | None | Annual sale; deed counties |
| IL | **Lien Cert** | SRI (iltaxsale.com) / county-direct | Cook County bulk download (monthly) | 18% (36% penalty) | — | Cook: largest sale in US; Scavenger sale every 2yr for older liens |
| IN | **Lien Cert** | SRI (sriservices.com) statewide | No | 25% (penalty, not rate) | — | SRI is dominant platform for most IN counties |
| IA | **Lien Cert** | GovEase / iowataxauction.com | iowatreasurers.org | — | — | Each county picks platform; June annual + monthly adjourned |
| KS | Tax Deed | County-direct | No | — | None | Deed state |
| KY | **Lien Cert** | County-direct / SRI (some) | No | 12% | — | Certificate of Delinquency sold to 3rd party purchasers |
| LA | Tax Deed | Parish-direct | No | — | 3 years | Called "tax sales"; 3yr redemption period |
| ME | Tax Lien → Deed | Municipality-direct | No | — | 18 months | Lien then quitclaim deed after 18mo |
| MD | **Lien Cert** | County-direct / online | No | 6-24% (varies by county) | — | Bid rate down; major counties use online auctions |
| MA | Tax Lien → Deed | Municipality-direct | No | 16% | — | Tax taking process |
| MI | Tax Deed | Bid4Assets | No | — | None | Foreclosure judgment, then auction; Wayne County = largest |
| MN | Tax Forfeited | State MN Dept of Admin (minnbidapi) | No | — | None | "Tax forfeited" not "tax deed"; state takes title, counties sell |
| MS | **Lien Cert** | County-direct | No | 18% | — | Annual August sale |
| MO | **Hybrid** | County-direct (Sheriff sale) | No | — | 1 year | St. Louis City/County = deed; some others = cert |
| MT | Tax Lien → Deed | County-direct | No | 10% | — | Certificate then lien deed after 5yr |
| NE | **Lien Cert** | County-direct | No | 14% | — | Annual March sale |
| NV | Tax Deed | County-direct | No | — | None | Annual deed sale |
| NH | Tax Lien → Deed | Municipality-direct | No | 18% | — | Deeding after 2yr |
| NJ | **Lien Cert** | newjerseytaxsale.com (municipality) | No | 18% | — | **565 municipalities each run own sale** — no county-level aggregation |
| NM | Tax Deed | State (NM Taxation & Revenue) | No | — | None | State-administered; unusual structure |
| NY | **Hybrid** | County-direct / auction.com | No | 18% | — | NYC = "in rem" foreclosure; upstate counties vary |
| NC | Tax Deed | County-direct | No | — | None | Upset bid process; 10 days for overbid |
| ND | Tax Lien → Deed | County-direct | No | 9% | — | 3yr redemption then deed |
| OH | **Lien Cert** | SRI / county-direct | No | 18% | — | Certificate of Delinquency; foreclosure action if unpaid |
| OK | Tax Deed | County-direct | No | — | None | Annual October sale |
| OR | Tax Deed | County-direct (courthouse) | Tillamook county list of all OR counties | — | None | In-person courthouse auctions typical; online rare |
| PA | Tax Deed | Upset sale → Judicial sale | No | — | None | 2-stage process: upset sale then repository |
| RI | Tax Lien → Deed | Municipality-direct | No | 10% | — | Certificate then deed |
| SC | **Lien Cert** | County-direct / online | No | 12% | — | Annual October sale |
| SD | Tax Lien → Deed | County-direct | No | 10% | — | 3yr redemption then deed |
| TN | Tax Deed | County-direct / courthouse | No | — | None | Chancery court sale typical |
| TX | **Tax Redeemable Deed** | LGBS (taxsales.lgbs.com) / Bid4Assets / PBFCM / MVBA | No | — | 2yr (homestead/ag) / 6mo (others) | Redeemable deed = investor gets deed but owner can redeem; monthly sales |
| UT | Tax Deed | County-direct / online | No | — | None | Annual May sale |
| VT | **Lien Cert** | Municipality-direct | No | 12% | — | Town-level (not county) |
| VA | Tax Deed | Commissioner of Accounts / courthouse | No | — | None | Judicial sale; low volume |
| WA | Tax Deed | Bid4Assets (most counties) | No | — | None | Annual or semi-annual; Bid4Assets dominant |
| WV | Tax Lien → Deed | State Auditor / county | No | 12% | — | Statewide sale + county delinquent list |
| WI | Tax Deed | County-direct | No | — | None | Tax deed after 2yr delinquency |
| WY | **Lien Cert** | County-direct | No | 15% | — | Annual November sale |

---

## D.2 — County Source Map

### Format Reference

| Field | Description |
|-------|-------------|
| `instrument` | `lien_cert` \| `tax_deed` \| `redeemable_deed` \| `hybrid` |
| `primary_url` | Official county tax collector/treasurer page for lien/deed info |
| `bulk_download` | Y/N — CSV/Excel/PDF list of delinquent parcels available for download |
| `bulk_url` | Direct download URL (if applicable) |
| `open_data_api` | Y/N — Socrata, ArcGIS open data, or other structured API available |
| `open_data_url` | API endpoint or open data portal URL |
| `arcgis_parcel_url` | ArcGIS REST endpoint for parcel boundary/data layer |
| `auction_platform` | Platform used for auctions |
| `auction_url` | Direct URL to auction listings |
| `auction_frequency` | `annual` \| `semi-annual` \| `monthly` \| `continuous` |
| `post_sale_redemption_days` | Days owner can redeem after deed sale (0 = none) |
| `notes` | Special considerations for crawling or data access |

---

## D.3 — Florida (FL) — Tax Lien Certificate

**State overview:** Annual mandatory cert sale by June 1 (FS 197.402). Interest rate 0–18%, bid down competitively. After 2 years, cert holder can apply for tax deed sale (separate auction run by Clerk of Court, not Tax Collector). FL DOR publishes statewide county-by-county sale info annually.

**State resource:** [FL DOR 2025 Tax Cert Sale Info](https://floridarevenue.com/property/Documents/2025TaxCertSale.pdf)

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Miami-Dade | https://www.miamidade.gov/taxcollector/ | TBD | TBD | TBD | LienHub | https://lienhub.com/county/miami-dade | Annual (May/June) | Largest county in FL by volume |
| Broward | https://www.broward.org/RecordsTaxesTreasury/TaxPayments/Pages/TaxCertificateSale.aspx | TBD | TBD | TBD | LienHub | https://lienhub.com/county/broward | Annual (May/June) | |
| Palm Beach | https://www.pbctax.gov/taxes/property-tax/tax-certificates-and-deeds/ | TBD | TBD | TBD | RealAuction | https://palm-beach.realtaxdeed.com | Annual (May/June) | RealAuction confirmed; deed sales also via RealAuction |
| Hillsborough | https://www.hillstaxfl.gov/taxes/tax-certificate/ | TBD | TBD | TBD | LienHub | https://lienhub.com/county/hillsborough | Annual (May/June) | LienHub confirmed in FL DOR 2025 doc |
| Orange | https://www.octaxcol.com/taxes/about-property-tax/tax-certificate-deed-sales/ | TBD | TBD | TBD | LienHub | https://lienhub.com/county/orange | Annual (May/June) | Tax deed sales handled by Clerk via RealAuction separately |

> **Tax Deed Sales (FL):** After cert goes unpaid 2yr, Clerk of Court runs a separate deed auction via RealAuction at `[county].realtaxdeed.com`. The cert sale (Tax Collector) and deed sale (Clerk) are two separate processes and data sources.

---

## D.4 — Arizona (AZ) — Tax Lien Certificate

**State overview:** Annual sale typically in February. Interest rate bid down from 16% maximum. Maricopa uses its own branded RealAuction subdomain. Parcel data available via county ArcGIS portals.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Maricopa | https://treasurer.maricopa.gov/taxlienweb/ | TBD | Y — Lien/Delinquent parcels GIS | https://experience.arcgis.com/experience/bd50c51b89054238bfadf69e91b421c9 | RealAuction | https://maricopa.arizonataxsale.com | Annual (Feb) | Delinquent parcel ArcGIS experience confirmed |
| Pima | https://www.to.pima.gov/taxLienSale/ | TBD | TBD | https://gis.pima.gov/maps/landbase/parsrch.htm | RealAuction | https://pima.arizonataxsale.com | Annual (last week Feb) | 16% start rate confirmed; RealAuction confirmed |
| Pinal | https://www.pinalcountyaz.gov/Departments/Treasurer/Pages/TaxLienSale.aspx | TBD | TBD | TBD | RealAuction | TBD | Annual (Feb) | |
| Yavapai | https://www.yavapai.us/treasurer | TBD | TBD | TBD | RealAuction | TBD | Annual (Feb) | |
| Mohave | https://www.mohavecounty.us/ContentPage.aspx?id=230 | TBD | TBD | TBD | RealAuction | TBD | Annual (Feb) | |

---

## D.5 — New Jersey (NJ) — Tax Lien Certificate

**State overview:** ⚠️ Highly decentralized — **565 municipalities** each hold their own annual tax sale. There is NO county-level aggregation. The Discovery Agent must target individual municipalities, not counties. Most use the `newjerseytaxsale.com` platform (format: `[municipality].newjerseytaxsale.com`). Interest rate bid down from 18%.

| Municipality | County | Primary Source URL | Auction Platform | Auction URL | Notes |
|-------------|--------|-------------------|-----------------|-------------|-------|
| Newark | Essex | https://www.newarknj.gov | newjerseytaxsale.com | https://newark.newjerseytaxsale.com | Largest NJ municipality by volume |
| Jersey City | Hudson | https://www.jerseycitynj.gov | newjerseytaxsale.com | https://jerseycity.newjerseytaxsale.com | |
| Trenton | Mercer | https://www.trentonnj.org | newjerseytaxsale.com | TBD | |
| Paterson | Passaic | https://www.patersonnjcity.gov | newjerseytaxsale.com | TBD | |
| Elizabeth | Union | https://www.elizabethnj.org/191/Tax-Sale | newjerseytaxsale.com | TBD | |

> **Discovery strategy for NJ:** Aloha should target the NJ Tax Collectors & Treasurers Association list for upcoming municipal sales, plus monitor `newjerseytaxsale.com` for registered upcoming auctions. Do not try to enumerate all 565 municipalities at once.

---

## D.6 — Colorado (CO) — Tax Lien Certificate

**State overview:** Annual sale October–November (varies by county). Interest rate set annually by State Bank Commissioner (14% for 2025). All major counties use RealAuction with `[county].coloradotaxsale.com` subdomains.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Denver | https://www.denvergov.org/Government/Agencies-Departments-Offices/Agencies-Departments-Offices-Directory/Treasury | TBD | Y — Denver Open Data | TBD | RealAuction | https://denver.coloradotaxsale.com | Annual (Nov) | Denver is a city-county; combined govt |
| El Paso | https://treasurer.elpasoco.com/county-treasurer/tax-lien-sale/ | TBD | TBD | TBD | RealAuction | https://elpaso.coloradotaxsale.com | Annual (Oct) | Oct 22, 2025 confirmed; registration opens Sep 24 |
| Arapahoe | https://www.arapahoeco.gov/your_county/county_departments/treasurer/tax_lien_sale/ | TBD | TBD | TBD | RealAuction | https://arapahoe.coloradotaxsale.com | Annual (Nov) | Nov 6, 2025 confirmed; 14% rate |
| Jefferson | https://www.jeffco.us/1468/Tax-Lien-Sale | TBD | TBD | TBD | RealAuction | https://jefferson.coloradotaxsale.com | Annual (Oct/Nov) | |
| Adams | https://www.adcogov.org/tax-lien-sale | TBD | TBD | TBD | RealAuction | https://adams.coloradotaxsale.com | Annual (Oct/Nov) | |

---

## D.7 — Illinois (IL) — Tax Lien Certificate

**State overview:** Annual tax sale; Cook County is the largest in the US. Smaller counties use SRI (iltaxsale.com). Cook County uses its own process (plus a Scavenger Sale for older liens). Cook County Clerk provides **bulk download** of delinquent property file updated monthly — one of the best open data sources for any county in the US.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Cook | https://www.cookcountytreasurer.com/taxsalegeneralinformation.aspx | **Y** — monthly delinquent file | **Y** — https://datacatalog.cookcountyil.gov/Property-Taxation/Treasurer-Annual-Tax-Sale/55ju-2fs9 | TBD | SRI / County-direct | https://www.iltaxsale.com | Annual (Dec 2026 next — delayed by law) | Best open data county in US; Scavenger sale every 2yr |
| DuPage | https://www.dupagecounty.gov/elected_officials/treasurer/tax_sale_information.php | TBD | TBD | TBD | SRI | https://www.iltaxsale.com | Annual | |
| Lake | https://www.lakecountyil.gov/2089/Tax-Sale | TBD | TBD | TBD | SRI | https://www.iltaxsale.com | Annual | |
| Will | https://www.willcountyillinois.com/Government/Elected-Officials/County-Treasurer | TBD | TBD | TBD | SRI | https://www.iltaxsale.com | Annual | |
| Kane | https://www.countyofkane.org/Departments/Treasurer/Pages/Tax-Sale.aspx | TBD | TBD | TBD | SRI | https://www.iltaxsale.com | Annual | |

---

## D.8 — Iowa (IA) — Tax Lien Certificate

**State overview:** Annual June sale + monthly adjourned sales through following May. Each county selects its own platform. Statewide registration portal: iowatreasurers.org. Interest rate varies.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Polk | https://www.polkcountyiowa.gov/treasurer/information-for-tax-sale-buyers/ | TBD | TBD | TBD | **GovEase** | https://www.govease.com | Annual June + monthly adjourned | GovEase confirmed; 11 adjourned sales per year |
| Linn | https://www.linncountyiowa.gov/1842/2025-Tax-Sale-Rules | TBD | TBD | TBD | iowataxauction.com | https://www.iowataxauction.com | Annual June | iowataxauction.com confirmed |
| Scott | https://www.scottcountyiowa.gov/treasurer/tax-sale | TBD | TBD | TBD | iowatreasurers.org | https://www.iowatreasurers.org | Annual June | |
| Johnson | https://www.johnsoncountyiowa.gov/treasurer | TBD | TBD | TBD | TBD | TBD | Annual June | |
| Black Hawk | https://www.blackhawkcounty.iowa.gov/departments/treasurer | TBD | TBD | TBD | TBD | TBD | Annual June | |

---

## D.9 — Texas (TX) — Tax Redeemable Deed

**State overview:** ⚠️ Texas is a **redeemable deed** state, not a pure deed state. The investor wins a deed at auction but the prior owner has a right of redemption:
- **Homestead / agricultural:** 2-year redemption
- **All other property:** 6-month redemption

Sales are typically monthly at courthouse steps (1st Tuesday of month) and managed by delinquent tax attorneys (not the county directly). Major law firms:
- **LGBS** (Linebarger Goggan Blair & Sampson): taxsales.lgbs.com — largest, represents most major TX counties
- **PBFCM** (Perdue, Brandon, Fielder, Collins & Mott): pbfcm.com
- **MVBA** (McCreary, Veselka, Bragg & Allen): mvbalaw.com/tax-sales/

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Harris | https://www.hctax.net | TBD | TBD | TBD | LGBS | https://taxsales.lgbs.com | Monthly (1st Tue) | LGBS represents Harris; list updated ~18 days pre-sale |
| Dallas | https://www.dallascounty.org/departments/tax/sheriff-sales.php | TBD | TBD | TBD | Sheriff / LGBS | https://taxsales.lgbs.com | Monthly (1st Tue) | Sheriff's Writ Enforcement Section runs sale |
| Tarrant | https://www.tarrantcountytx.gov/en/tax/property-tax/public-auctions.html | TBD | TBD | TBD | **Bid4Assets** | https://www.bid4assets.com | Monthly | Bid4Assets confirmed for Tarrant; multiple auctions verified |
| Bexar | https://www.bexar.org/1529/Property-Tax | TBD | TBD | TBD | LGBS | https://taxsales.lgbs.com | Monthly (1st Tue) | LGBS confirmed for Bexar |
| Travis | https://www.traviscountytx.gov/tax-office | TBD | TBD | TBD | LGBS / PBFCM | https://taxsales.lgbs.com | Monthly (1st Tue) | Austin area; may use PBFCM |

---

## D.10 — Georgia (GA) — Tax Deed

**State overview:** Tax deed sale after delinquency. Prior owner has **12-month right of redemption** for homestead property. County tax commissioner runs the sale. Fulton County has open GIS parcel data.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Fulton | https://www.fultoncountytaxes.org | TBD | **Y** — https://gisdata.fultoncountyga.gov/datasets/tax-parcels | https://gisdata.fultoncountyga.gov | County-direct | TBD | Monthly | Open GIS parcel data confirmed |
| Gwinnett | https://www.gwinnettcounty.com/web/gwinnett/departments/financialservices/taxcommissioner | TBD | TBD | TBD | County-direct | TBD | Monthly | |
| DeKalb | https://publicaccess.dekalbtax.org | TBD | TBD | TBD | County-direct | https://publicaccess.dekalbtax.org/forms/htmlframe.aspx?mode=content/search/tax_sale_listing.html | Monthly | Public access portal with tax sale listing confirmed |
| Cobb | https://www.cobbtax.org | TBD | TBD | TBD | County-direct | TBD | Monthly | |
| Clayton | https://www.claytoncountyga.gov/government/tax-commissioner | TBD | TBD | TBD | County-direct | TBD | Monthly | |

---

## D.11 — Michigan (MI) — Tax Deed

**State overview:** County Treasurer foreclosures under the Michigan General Property Tax Act. After judgment, properties are auctioned. **Wayne County** is the largest tax deed auction in the midwest — consistently hundreds of properties annually. Bid4Assets is the dominant statewide platform.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Wayne | https://www.waynecountymi.gov/Government/Elected-Officials/Treasurer/Auctions-Claims | TBD | TBD | TBD | **Bid4Assets** | https://www.bid4assets.com/wayne | Annual (September) | Online sale starts Sep 16 confirmed; largest MI auction |
| Oakland | https://www.oakgov.com/fiscal/treasurer | TBD | TBD | TBD | Bid4Assets / auction.com | TBD | Annual | |
| Macomb | https://www.macombgov.org/departments/treasurers-office/tax-foreclosure/auction-and-claims | TBD | TBD | TBD | County-direct | TBD | Annual | |
| Kent | https://www.accesskent.com/Departments/Treasurer/ | TBD | TBD | TBD | TBD | TBD | Annual | |
| Genesee | https://www.geneseecounty.org/offices/treasurer | TBD | TBD | TBD | TBD | TBD | Annual | |

---

## D.12 — Minnesota (MN) — Tax Forfeited Land

**State overview:** Minnesota uses "tax forfeiture" (not "tax deed"). After delinquency, the state takes title, and county auditors sell the land through the MN Department of Administration's online auction system (minnbidapi). Properties must be approved for sale by state DNR and county board.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Hennepin | https://www.hennepin.us/residents/property/tax-forfeited-land | TBD | TBD | TBD | MN Dept of Admin | https://minnbidapi-prod.ecommerce.auction | Periodic (as properties available) | County lists available inventory; state runs auction |
| Ramsey | https://www.ramseycountymn.gov/residents/property-home/taxes-values/productive-properties/tax-forfeited-public-sales | TBD | TBD | TBD | MN Dept of Admin | https://minnbidapi-prod.ecommerce.auction | Periodic | Online auction Feb–Mar 2026 confirmed |
| Dakota | https://www.co.dakota.mn.us/HomeProperty/TaxForfeited/ | TBD | TBD | TBD | MN Dept of Admin | TBD | Periodic | |
| Anoka | https://www.anokacounty.us/773/Forfeited-Land | TBD | TBD | TBD | MN Dept of Admin | TBD | Periodic | |
| Washington | https://www.co.washington.mn.us/1110/Tax-Forfeited-Lands | TBD | TBD | TBD | MN Dept of Admin | TBD | Periodic | |

---

## D.13 — Washington (WA) — Tax Deed

**State overview:** County Treasurer forecloses and sells via annual auction. Bid4Assets is the dominant platform for major WA counties. No post-sale redemption period.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| King | https://kingcounty.gov/en/dept/executive-services/buildings-property/treasury-operations/tax-foreclosures/auctions | TBD | TBD | TBD | County-direct | https://kingcounty.gov/foreclosure | Annual (Sep) | Next auction Sep 9, 2026; county-direct (not Bid4Assets) |
| Pierce | https://www.piercecountywa.gov/716/Foreclosure | TBD | TBD | TBD | **Bid4Assets** | https://www.bid4assets.com/storefront/PierceATNov25 | Annual (Nov) | Bid4Assets confirmed; $1,000 deposit + $35 fee |
| Snohomish | https://snohomishcountywa.gov/220/Tax-Foreclosures | TBD | TBD | TBD | **Bid4Assets** | https://www.bid4assets.com | Annual (Nov) | Nov 18, 2025 confirmed; Deed Wizard on Bid4Assets |
| Spokane | https://www.spokanecounty.org/426/Treasurer | TBD | TBD | TBD | TBD | TBD | Annual | |
| Clark | https://www.clark.wa.gov/treasurer | TBD | TBD | TBD | TBD | TBD | Annual | |

---

## D.14 — Oregon (OR) — Tax Deed

**State overview:** County-level tax foreclosure; in-person courthouse auctions typical. Online auctions rare. Tillamook County maintains a list of all Oregon counties' land sale websites. No post-sale redemption.

| County | Primary Source URL | Bulk Download | Open Data API | ArcGIS Parcel | Auction Platform | Auction URL | Auction Freq | Notes |
|--------|-------------------|---------------|---------------|---------------|-----------------|-------------|-------------|-------|
| Multnomah | https://www.multco.us/tax-title | TBD | TBD | TBD | County-direct | TBD | Annual (Spring) | Next auction Spring 2026; county-direct |
| Washington | https://www.co.washington.or.us/treasurer | TBD | TBD | TBD | County-direct | TBD | Annual | |
| Clackamas | https://www.clackamas.us/at/foreclosure.html | TBD | TBD | TBD | Courthouse (in-person) | https://apps.clackamas.us/surplusproperty/ | Annual (Dec) | 48 properties Dec 18, 2025; in-person only; 100 person cap |
| Lane | https://www.lanecountyor.gov/treasurer | TBD | TBD | TBD | County-direct | TBD | Annual | |
| Marion | https://www.co.marion.or.us/AO/Treasurer | TBD | TBD | TBD | County-direct | TBD | Annual | |

> **All OR county land sale sites:** https://www.tillamookcounty.gov/assessment/page/oregon-county-land-sale-websites

---

## D.15 — Secondary Lien Certificate States

### Indiana (IN) — Tax Lien Certificate
SRI (sriservices.com) is the dominant platform for most Indiana counties. Annual sale.

| County | Primary Source URL | Auction Platform | Auction URL | Notes |
|--------|-------------------|-----------------|-------------|-------|
| Marion | https://www.indy.gov/activity/taxes-and-assessments/tax-sale | SRI | https://www.sriservices.com | Indianapolis; largest IN county |
| Lake | https://www.lakecountyin.org/treasurer | SRI | https://www.sriservices.com | |
| Allen | https://www.allencounty.us/treasurer | SRI | https://www.sriservices.com | Fort Wayne |
| Hamilton | https://www.hamiltoncounty.in.gov/treasurer | SRI | https://www.sriservices.com | Fast-growing suburb of Indianapolis |
| Tippecanoe | https://www.tippecanoe.in.gov/treasurer | SRI | https://www.sriservices.com | Lafayette |

### Maryland (MD) — Tax Lien Certificate
County-level sales, online. Interest rate varies 6–24% by county. Annual May–June sale.

| County | Primary Source URL | Auction Platform | Notes |
|--------|-------------------|-----------------|-------|
| Montgomery | https://www.montgomerycountymd.gov/finance/taxes/tax-sale.html | County-direct / online | Largest MD county |
| Prince George's | https://www.princegeorgescountymd.gov/Government/AgencyIndex/Finance/Property-Tax-Billing/Tax-Sale | County-direct / online | |
| Baltimore County | https://www.baltimorecountymd.gov/departments/budfin/taxsale | County-direct / online | |
| Baltimore City | https://taxsale.baltimorecity.gov | County-direct / online | City-county; own dedicated tax sale site |
| Anne Arundel | https://www.aacounty.org/departments/finance/tax-sale | County-direct / online | |

### Kentucky (KY) — Tax Lien Certificate
Certificate of Delinquency sold to 3rd party purchasers. Rate up to 12%. County clerk-level.

| County | Primary Source URL | Notes |
|--------|-------------------|-------|
| Jefferson | https://jeffersoncc.ky.gov | Louisville; largest KY county |
| Fayette | https://www.fayettecountyky.gov | Lexington |
| Kenton | https://www.kentoncounty.org | Northern KY / Cincinnati metro |

---

## D.16 — Secondary Tax Deed States

### California (CA) — Tax Deed
No right of redemption post-sale. Counties manage independently; some use auction.com, some direct.

| County | Primary Source URL | Auction Platform | Notes |
|--------|-------------------|-----------------|-------|
| Los Angeles | https://ttc.lacounty.gov/tax-defaulted-property-auctions/ | auction.com | Largest county in US; major volume |
| San Diego | https://www.sdttc.com/content/ttc/en/tax-collection/auctions.html | auction.com | |
| Orange | https://www.octreasurer.gov/property-tax/property-tax-defaulted-property-sales | auction.com | |
| Riverside | https://www.countyofriverside.us/government/departments-offices/treasurer-tax-collector/property-tax/defaulted-tax-sales | auction.com | |
| San Bernardino | https://www.sbcounty.gov/atc/tax-defaulted-property-sales/ | auction.com | |

### Tennessee (TN) — Tax Deed
Chancery court sale typical. County Trustee manages delinquent list.

| County | Primary Source URL | Notes |
|--------|-------------------|-------|
| Shelby | https://www.shelbycountytrustee.com | Memphis area |
| Davidson | https://www.nashville.gov/departments/finance/assessments/tax-sales | Nashville; city-county consolidated |
| Knox | https://www.knoxcounty.org/trustee | Knoxville |

### North Carolina (NC) — Tax Deed
Upset bid process: after initial sale, 10-day window for overbids. Multiple rounds possible.

| County | Primary Source URL | Notes |
|--------|-------------------|-------|
| Mecklenburg | https://www.mecknc.gov/TaxCollector/Pages/RealPropertySales.aspx | Charlotte area; largest NC county |
| Wake | https://www.wake.gov/departments-agencies/tax-administration/tax-foreclosures-sales | Raleigh area |
| Guilford | https://www.guilfordcountync.gov/our-county/tax/foreclosure-properties | Greensboro |

---

## D.17 — Hybrid States

### Missouri (MO) — Hybrid
Instrument varies by county. St. Louis City and County use a deed-like collector's deed process. Monthly sales typical.

| County | Instrument | Primary Source URL | Notes |
|--------|-----------|-------------------|-------|
| St. Louis County | Cert + Deed | https://stlouiscountymotaxcollector.com | Both instruments used; annual cert sale then deed if unpaid |
| St. Louis City | Deed | https://stlouis-mo.gov/government/departments/collector/ | City-county; collector's deed process |
| Jackson | Deed | https://www.jacksongov.org/our-county/departments/collection/tax-certificate-sales | Kansas City area |
| St. Charles | Cert | https://www.sccmo.org/collector | Growing suburb of St. Louis |

### New York (NY) — Hybrid
NYC uses "in rem" foreclosure (unique process). Upstate counties vary — some lien cert, some deed.

| County/Area | Instrument | Primary Source URL | Notes |
|------------|-----------|-------------------|-------|
| New York City (5 boroughs) | In Rem | https://www.nyc.gov/site/finance/property/property-lien-sales.page | NYC Lien Sale: city bundles liens and sells to a trust annually |
| Nassau | Lien Cert | https://www.nassaucountyny.gov/agencies/Treasurer/ | Suburban NYC; high-value liens |
| Suffolk | Lien Cert | https://www.suffolkcountyny.gov/Departments/Treasurer | Long Island |
| Westchester | Lien Cert | https://westchestercountyny.gov/government/departments/finance | |
| Monroe | Lien Cert | https://www.monroecounty.gov/treasury | Rochester area |

### Ohio (OH) — Lien Certificate (Certificate of Delinquency)
SRI is common platform. Foreclosure action required if unpaid — not a self-executing lien.

| County | Primary Source URL | Auction Platform | Notes |
|--------|-------------------|-----------------|-------|
| Franklin | https://www.franklincountyauditor.com | SRI / county-direct | Columbus area |
| Cuyahoga | https://treasurer.cuyahogacounty.us | SRI / county-direct | Cleveland area; large volume |
| Hamilton | https://www.hamiltoncountyohio.gov/government/departments/treasurer | SRI | Cincinnati area |
| Summit | https://www.summitoh.net/treasurer | SRI | Akron area |
| Montgomery | https://www.mcohio.org/government/elected_officials/treasurer | SRI | Dayton area |

---

## D.18 — Data Source Priority for Discovery Agent

When targeting any county, the Discovery Agent should attempt sources in this order:

```
1. Socrata / county open data API           → structured, zero crawl needed
2. ArcGIS Feature Service (REST query)      → structured, queryable
3. County bulk download (CSV/Excel/PDF)     → download once, parse
4. Online auction platform API/listing      → Bid4Assets, LienHub, GovEase, SRI, RealAuction
5. County tax collector web page crawl      → crawl4ai for static, agent-browser for JS-heavy
6. County clerk / recorder web page crawl  → for deed sale listings
7. Third-party aggregator (PropStream)      → fallback; paid API preferred over scraping
```

---

## D.19 — Platform Quick Reference

| Platform | URL | Instrument | States/Coverage | Data Access Method |
|----------|-----|-----------|----------------|-------------------|
| LienHub | lienhub.com | Lien Cert | FL (primary) | Web crawl; county subpages |
| RealAuction | realtaxdeed.com / [county].coloradotaxsale.com / [county].arizonataxsale.com | Lien Cert + Deed | FL, AZ, CO, NJ (some), others | Web crawl; registration required to see full list |
| GovEase | govease.com | Lien Cert | IA, and growing | Web crawl |
| SRI | sriservices.com / iltaxsale.com | Lien Cert | IL, IN, OH, and others | Web crawl |
| iowataxauction.com | iowataxauction.com | Lien Cert | IA (Linn Co and others) | Web crawl |
| Bid4Assets | bid4assets.com | Tax Deed | TX (Tarrant), MI (Wayne), WA (Pierce, Snohomish), GA (some) | Web crawl; storefront pages per county |
| LGBS | taxsales.lgbs.com | Redeemable Deed | TX (Harris, Dallas, Bexar, Travis, and many others) | Web crawl; updated ~18 days pre-sale |
| PBFCM | pbfcm.com | Redeemable Deed | TX (some counties) | Web crawl |
| MVBA | mvbalaw.com/tax-sales/ | Redeemable Deed | TX (some counties) | Web crawl |
| MN Bid API | minnbidapi-prod.ecommerce.auction | Tax Forfeited | MN (statewide) | Web crawl |
| newjerseytaxsale.com | newjerseytaxsale.com | Lien Cert | NJ (municipalities) | Web crawl; [muni].newjerseytaxsale.com |
| FL DOR 2025 list | floridarevenue.com/property/Documents/2025TaxCertSale.pdf | Lien Cert | FL | PDF download + parse annually |
| OR county list | tillamookcounty.gov/assessment/page/oregon-county-land-sale-websites | Tax Deed | OR (all counties) | Reference page; links to county sites |

---

## D.20 — TBD Fields Completion Plan

Fields marked `TBD` in tables above should be filled in as counties are actively targeted. For each county onboarded:

1. Run `GET https://[county].[state].gov/...ArcGIS/rest/services` to enumerate ArcGIS layers — find the `Parcels` or `TaxParcels` layer
2. Search `data.socrata.com` and `opendata.[county].gov` for parcel/tax datasets
3. Check the county's main tax collector page for any "download" or "bulk data" links
4. Log confirmed URLs to this document before the county goes into production crawling

---

*Sources: FL DOR, Maricopa Treasurer, Pima Treasurer, Cook County Clerk open data, Iowa County Treasurers, Tarrant County / Bid4Assets auction records, Wayne County Treasurer / Bid4Assets, Pierce County / Bid4Assets, Snohomish County / Bid4Assets, King County Treasury, Clackamas County Property Disposition, Multnomah County Tax Title, Ramsey County Productive Properties, RealAuction platform confirmations, LGBS taxsales platform, Tillamook County OR county list*
