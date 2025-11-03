# SaveTaxInvestments
Website that helps to make tax efficient investments, only applicable under german tax legislation


# Frontend
simple web-based form to enter the ISIN (international ID number) of your ETF and your personal tax exempt amount.

# Backend
searches for the entered ISIN in the database and performs the calculation. Afterwards it outputs the result to the frontend. 

# Database
All data about all investable ETFs in germany was scraped from a well known website and stored in Supabase.
