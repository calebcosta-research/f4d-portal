from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

from model import Base

load_dotenv()

def create_session():
    # Replace these values with your actual database connection details
    username =  os.environ.get('sql_username')
    password = os.environ.get('sql_password')
    host = os.environ.get('sql_host')
    database = os.environ.get('sql_database')
    port = os.environ.get('sql_port')

    # Connection string for SQL Server with specified schema
    #connection_string = f"mssql+pyodbc://{username}:{password}@{host}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
    
    from urllib.parse import quote_plus

    connection_string = (
        f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
        f"?driver={quote_plus('ODBC Driver 17 for SQL Server')}"
        f"&fast_executemany=true"
    )
    # Create an engine
    engine = create_engine(connection_string)

    # Create the indicators table
    Base.metadata.create_all(engine)

    # Create a session
    Session = sessionmaker(bind=engine)
    return Session()



# def create_session():
#     # SQLite database file
#     database = 'f4d.db'  # Name of your SQLite database file

#     # Connection string for SQLite
#     connection_string = f"sqlite:///{database}"

#     # Create an engine
#     engine = create_engine(connection_string)

#     # Create the indicators table
#     Base.metadata.create_all(engine)

#     # Create a session
#     Session = sessionmaker(bind=engine)
#     return Session()
