from dotenv import load_dotenv


from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

load_dotenv()
password = os.getenv("MY_SUPABASE_PASSWORD")
# Update with your actual password
SUPABASE_URL = f"postgresql://postgres.kbgxllapsgxeslmmnocx:{password}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

Base = declarative_base()

class EtfAusschuettend(Base):
    """
    SQLAlchemy model for the etf_ausschuettend table.
    """
    __tablename__ = 'etf_ausschuettend'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    ter = Column(String)
    ytd = Column(String)
    fondsgröße  = Column(String)
    auflagedatum = Column(String)
    ausschüttung = Column(String)
    replikation = Column(String)
    isin = Column(String, unique=True, index=True)
    dividendenrendite = Column(String)
    __table_args__ = (UniqueConstraint('isin', name='_isin_uc'),)

def get_engine_and_session(db_url):
    """
    Returns SQLAlchemy engine and sessionmaker for the given db_url.
    """
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return engine, Session

def create_table_if_not_exists(engine):
    """
    Creates the etf_ausschuettend table if it does not exist.
    """
    Base.metadata.create_all(engine)

def insert_etf_entries(etf_entries, db_url):
    """
    Inserts or updates a list of ETF dicts into the database.
    If an ETF with the same ISIN exists, it will be updated with the new data.
    Args:
        etf_entries (list of dict): List of ETF data dicts.
        db_url (str): SQLAlchemy database URL.
    Returns:
        None
    """
    engine, Session = get_engine_and_session(db_url)
    create_table_if_not_exists(engine)
    session = Session()
    
    updated_count = 0
    inserted_count = 0
    
    for etf in etf_entries:
        if not etf.get('isin'):
            continue
            
        # Create new entry
        entry = EtfAusschuettend(
            name=etf.get('name', ''),
            ter=etf.get('ter', ''),
            ytd=etf.get('ytd', ''),
            fondsgröße=etf.get('fondsgröße', ''),
            auflagedatum=etf.get('auflagedatum', ''),
            ausschüttung=etf.get('ausschüttung', ''),
            replikation=etf.get('replikation', ''),
            isin=etf.get('isin', ''),
            dividendenrendite=etf.get('dividendenrendite', ''),
        )
        
        # Check if entry exists
        existing = session.query(EtfAusschuettend).filter_by(isin=etf['isin']).first()
        if existing:
            # Update existing entry
            for key, value in etf.items():
                setattr(existing, key, value)
            updated_count += 1
        else:
            # Insert new entry
            session.add(entry)
            inserted_count += 1
    
    session.commit()
    session.close()
    print(f"Database update complete: {updated_count} entries updated, {inserted_count} new entries inserted.")

# Example usage:
# from scraper import parse_first_three_tables, scrape_etf_links, etc.
# etf_entries = ... # get list of dicts from your scraping logic
# insert_etf_entries(etf_entries, SUPABASE_URL)