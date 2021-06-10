import dask, glob, tqdm, json
import numpy as np
import pandas as pd
import itertools
import itertools as it
import multiprocessing
import dask.dataframe as dd
from dask.dataframe import from_pandas, read_json
from functools import partial
    
class AuthorInfos(object):
    __slots__ = ['birth_year', 'citation_count']
    
    def __init__(self, y, c):
        self.birth_year = y
        self.citation_count = c

    def to_dict(self):
        return {'birth_year': self.birth_year, 'citation_count': self.citation_count}


def get_authors_single_infos(row, valid_authors, author_infos, pair_authors, max_year):
    year = row['year']
    
    if not year or type(year) != type(1.0) or year < 1950:
        return
    
    if year > max_year:
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
    
    
    for a in authors_id:
        if a in valid_authors:
            if a in author_infos:
                current = author_infos[a]
                current.birth_year = min(current.birth_year, year)
                current.citation_count.append(total_cits)
                author_infos[a] = current
            else:
                foo = AuthorInfos(year, [total_cits])
                author_infos[a] = foo
  

    
def get_authors_infos(row, valid_authors, author_infos, pair_authors, max_year):
    year = row['year']
    
    if not year or type(year) != type(1.0) or year < 1950:
        return
    
    if year > max_year:
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
        
    for a1, a2 in itertools.combinations(authors_id, 2):
        if a1 in valid_authors:
            if a1 in pair_authors:
                if a2 in pair_authors[a1]:
                    pair_authors[a1][a2].append(total_cits)
                else:
                    pair_authors[a1][a2] = [total_cits]
            else:
                pair_authors[a1] = {a2: [total_cits]}
            
        if a2 in valid_authors:
            if a2 in pair_authors:
                if a1 in pair_authors[a2]:
                    pair_authors[a2][a1].append(total_cits)
                else:
                    pair_authors[a2][a1] = [total_cits]
            else:
                pair_authors[a2] = {a1: [total_cits]}


def work(valid, max_year, get_authors_infos, input_file):
    fidx = int(input_file.split('_')[-1])
    authors_infos = dict()
    pair_authors = dict()
    chunk = pd.read_csv(input_file, header=None, sep='\t',
            names=['paper_id', 'doi', 'year', 'authors', 'total_cits', 'cits'])
    chunk.dropna(0, subset=['authors', 'year'], inplace=True)
    
    if len(chunk) > 0:
        for _, row in chunk.iterrows():
            get_authors_infos(row, valid, authors_infos, pair_authors, max_year)
    else:
        print('chunk is empty', input_file)
    
    temp_ainfos = dict()
    for k,v in authors_infos.items():
        temp_ainfos[k] = v.to_dict()
    
#     with open('data/PairAuthors250_split/pair_%d_authors_valid_full_%05d' % (max_year, fidx), 'w') as outfile:
#         json.dump(pair_authors, outfile)
    with open('data/AuthorsInfosByYear/authors_infos_year_%d_valid_full_%05d' % (max_year, fidx), 'w') as outfile:
        json.dump(temp_ainfos, outfile)


def step_1():
    valid_authors = dask.dataframe.read_csv('data/valid_authors_full.txt', names=['author', 'paper', 'cits'], header=None)['author']
    valid_authors = valid_authors.apply(int)
    valid_list = []
    for v in tqdm.tqdm(valid_authors):
        valid_list.append(v)
    valid_list = set(valid_list)
    print(len(valid_list))
    del valid_authors

    files_input = glob.glob('data/PaperCompleteInfos_split/*')
    print('total of files', len(files_input))
    
    from tqdm.contrib.concurrent import process_map
    for max_year in range(1960, 2021, 10):
        print(max_year)
        process_map(partial(work, valid_list, max_year, get_authors_single_infos), files_input, max_workers=14)
        break

def step_2():
    for max_year in range(1960, 2021, 10):
        print(max_year)
        list_of_files = glob.glob('data/AuthorsInfosByYear/authors_infos_year_%d_valid_full_*' % max_year)
        output_write = open('data/authors_infos_to_sort_step2_%d' % max_year,'w')

        for filename in tqdm.tqdm(list_of_files):
            json_to_pd = json.load(open(filename))
            for k,v in json_to_pd.items():
                output_write.write("%s\t%d\t%s\n" % (k, v['birth_year'], v['citation_count']))
        output_write.close()

        
def step_2_5():
    
    def cits_to_merge(row):
        out = ''.join(row)
        out = out.replace('][', ', ')
        return out
    
    for max_year in range(1960, 2021, 10):
        to_merge = dd.read_csv('data/authors_infos_sorted_step_2_%d' % max_year, header=None, sep='\t', names=['authors_id', 'birth', 'citations'])
        
        collect_concat = dd.Aggregation(name='collect_concat',
            chunk=lambda s1: s1.apply(list),
            agg=lambda   s2: s2.apply(lambda chunks: list(it.chain.from_iterable(chunks))),
            finalize=lambda s3: s3.apply(lambda xx: ''.join(xx).replace('][', ', '))
        )
        output = to_merge.groupby('authors_id').agg({'birth': ['min'], 'citations': [collect_concat]})
        
        from dask.diagnostics import ProgressBar
        with ProgressBar():
            output.to_csv('data/authors_infos_full_final_%d' % max_year, header=None, sep='\t', single_file=True)       
        
        
def step_3():
    for max_year in range(1960, 2021, 10):
        print(max_year)
    
        files = sorted(glob.glob('data/PairAuthors250_split/pair_%d_authors_valid_full_*' % max_year))
        for i, file in tqdm.tqdm(enumerate(files), total=len(files)):
            t = []
            temp_json = json.load(open(file))
            for a1, hist in temp_json.items():
                for a2, cits in hist.items():
                    t.append((a1, a2, [int(c) for c in cits]))
            p = pd.DataFrame(t, columns=['a1', 'a2', 'cits'])
            p.to_csv('data/PairAuthors2csv_split/pair_%d_csv%05d' % (max_year,i), header=None, index=None, sep='\t')
            del t
            del temp_json
    
    
def step_4():
    # sort --parallel=20 pairs_csv_temp.csv s
    pass


def _step_5(input_file):
    chunk = pd.read_csv(input_file, header=None, error_bad_lines=False,
                    encoding='utf-8',
                    sep='\t', names=['a1_id', 'a2_id', 'cits'])
    
    authors = {}
    current_reference = chunk.iloc[0,0]
    idx = int(input_file.split('_')[-1])
    output = open(input_file.replace('part','merged_part'), 'w')
#     output = open(input_file[:-4] + 'processed_pairs.csv', 'w')
    for idx,row in chunk.iterrows(): # total=len(chunk):
        if type(row['cits']) != type(''):
            print(input_file)
            print(row)
            print('-----------')
            continue
            
        temp_json = json.loads(row['cits'])
        
        if current_reference == row['a1_id']:
            if row['a2_id'] in authors:
                authors[row['a2_id']] += temp_json
            else:
                authors[row['a2_id']] = temp_json
        else:
            output.write("%d\t%s\n" % (current_reference, json.dumps(authors)))
            current_reference = row['a1_id']
            authors = {row['a2_id']: temp_json}

    if len(authors) > 0:
        output.write("%d\t%s\n" % (current_reference, json.dumps(authors)))
            
    output.close()


def step_5():
    from tqdm.contrib.concurrent import process_map
    
    for max_year in [2000, 2010, 2020]:
#         files = glob.glob('data/pair_csv_%d_byAuthorID.csv' % max_year)
#         _step_5(files[0])

        files = glob.glob('data/PairAuthors2csv_split/pair_csv_year_%d_part_*' % max_year)
        print(files)
        N = len(files)
        
        process_map(_step_5, files, total=N, max_workers=14)


def join_dicts(a, b):
    A = json.loads(a)
    B = json.loads(b)
    for k,v in B.items():
        if k in A:
            A[k] += v
        else:
            A[k] = v
    
    return json.dumps(A)
    
    
def step_6():
    for max_year in [2020]:
        files = glob.glob('data/PairAuthors2csv_split/pair_csv_year_%d_merged_part*' % max_year)
        N = len(files)

        to_concat = []
        prev = pd.read_csv(files[0], header=None, sep='\t')
        for i in tqdm.tqdm(range(1, N), total=N):
            current = pd.read_csv(files[i], header=None, sep='\t')

            if prev.iloc[-1,0] == current.iloc[0,0]:
                current.iloc[0, 1] = join_dicts(current.iloc[0, 1], prev.iloc[-1, 1])

                prev = prev[:-1]

            prev.to_csv('data/PairAuthors2csv_split/pair_csv_year_%d_%50d' % (max_year, i-1), header=None, sep='\t')
            del prev
            prev = current

        prev.to_csv('data/PairAuthors2csv_split/pair_csv_year_%d_%50d' % (max_year, N-1), header=None, sep='\t')
    
    
    
if __name__ == '__main__':
#     step_1()
#     step_2()
#     step_2_5()
#     step_3()
#     step_4()
#     step_5()
    step_6()
