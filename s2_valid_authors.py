import glob, tqdm, json
import pandas as pd
import dask
import numpy as np
import itertools
import multiprocessing
from dask.dataframe import from_pandas
    

def get_authors_infos(row, author_infos, pair_authors):
    year = row['year']
    
    if not year or type(year) != type(1.0) or year < 1950:
        return
    
    total_cits = row['total_cits']
    if np.isnan(total_cits):
        total_cits = 0
    authors_id = row['authors']
    if type(authors_id) == type(' '):
        authors_id = set(authors_id.split(','))
        authors_id = sorted([int(a) for a in authors_id])
    else:
        authors_id = set([authors_id])
    
    if len(authors_id) > 10:
        return  

    for a in authors_id:
        if a in author_infos:
            author_infos[a] += 1
            pair_authors[a] += total_cits
        else:
            author_infos[a] = 1
            pair_authors[a] = total_cits     
            
            
def create_dataframe(authors_infos, pair_authors):
    df = pd.DataFrame({'author': list(authors_infos.keys()), 
                       'paper': list(authors_infos.values()),
                       'cits': list(pair_authors.values())})
    dd = from_pandas(df, npartitions=200)
    del authors_infos
    del pair_authors
    return dd


def work(input_file):
    authors_infos = dict()
    pair_authors = dict()
    chunk = pd.read_csv(input_file, header=None, sep='\t',
            names=['paper_id', 'doi', 'year', 'authors', 'total_cits', 'cits',])
    if len(chunk) > 0:
        for _, row in chunk.iterrows():
            get_authors_infos(row, authors_infos, pair_authors)
    else:
        print('chunk is empty', input_file)
    
    dataframe = create_dataframe(authors_infos, pair_authors)
    
    return dataframe


def step_1():
    files_input = glob.glob('data/PaperCompleteInfos_split/*')
    from tqdm.contrib.concurrent import process_map
    mapped = process_map(work, files_input, max_workers=16)

    authors = dask.dataframe.concat(mapped)
    authors = authors.groupby('author').sum().reset_index()
    print('total de autores', len(authors))
    temp = authors[authors['cits'] >= 200]
    temp = temp[authors['paper'] >= 10]
#     temp.to_csv('data/valid_authors_full.txt', header=False, single_file=True, index=False)

    
def step_2():
    dataframe = dask.dataframe.read_csv('data/valid_authors_full.txt', header=None)
    print(dataframe.head())
#     dataframe.sample(frac=0.1).to_csv('data/valid_authors_250000.txt', single_file=True)
    

if __name__ == '__main__':
#     split -l 3000000 -a -5 -d data/paper_complete_infos.csv data/PaperCompleteInfos_split/paper_comp_info_
#     step_1()
    step_2()