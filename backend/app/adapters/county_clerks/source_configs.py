from __future__ import annotations

from app.adapters.county_clerks.base_county_clerk_live import CountyClerkConfig

FLORIDA_COUNTY_CLERK_CONFIGS: tuple[CountyClerkConfig, ...] = (
    CountyClerkConfig("Miami-Dade", "FL", "https://www.miamidadeclerk.gov/", "manual_import"),
    CountyClerkConfig("Broward", "FL", "https://www.browardclerk.org/", "manual_import"),
    CountyClerkConfig("Palm Beach", "FL", "https://www.mypalmbeachclerk.com/", "manual_import"),
    CountyClerkConfig("Orange", "FL", "https://www.myorangeclerk.com/", "manual_import"),
    CountyClerkConfig("Hillsborough", "FL", "https://www.hillsclerk.com/", "manual_import"),
    CountyClerkConfig("Pinellas", "FL", "https://www.mypinellasclerk.gov/", "manual_import"),
    CountyClerkConfig("Duval", "FL", "https://www2.duvalclerk.com/", "manual_import"),
    CountyClerkConfig("Polk", "FL", "https://www.polkcountyclerk.net/", "manual_import"),
    CountyClerkConfig("Lee", "FL", "https://www.leeclerk.org/", "manual_import"),
    CountyClerkConfig("Collier", "FL", "https://www.collierclerk.com/", "manual_import"),
    CountyClerkConfig("Seminole", "FL", "https://www.seminoleclerk.org/", "manual_import"),
    CountyClerkConfig("Osceola", "FL", "https://www.osceolaclerk.com/", "manual_import"),
)
