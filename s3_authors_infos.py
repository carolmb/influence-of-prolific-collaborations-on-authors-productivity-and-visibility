import dask, glob, tqdm, json
import numpy as np
import pandas as pd
import itertools
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
    
    
#     for a in authors_id:
#         if a in valid_authors:
#             if a in author_infos:
#                 current = author_infos[a]
#                 current.birth_year = min(current.birth_year, year)
#                 current.citation_count.append(total_cits)
#                 author_infos[a] = current
#             else:
#                 foo = AuthorInfos(year, [total_cits])
#                 author_infos[a] = foo

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


def work(valid, max_year, input_file):
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
    
    with open('data/PairAuthors250_split/pair_%d_authors_valid_full_%05d' % (max_year, fidx), 'w') as outfile:
        json.dump(pair_authors, outfile)


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
        process_map(partial(work, valid_list, max_year), files_input, max_workers=14)


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
    output = open('data/PairAuthors2csv_split/pair_processed_%50d' % idx, 'w')
    for idx,row in chunk.iterrows():
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
    files = glob.glob('data/PairAuthors2csv_split/pair_sorted_*')
    N = len(files)

    from tqdm.contrib.concurrent import process_map
    process_map(_step_5, files, total=N, max_workers=14)


def join_dicts(a, b):
    A = json.loads(a)
    B = json.loads(b)
    for k,v in B.items():
        if k in a:
            A[k] += v
        else:
            A[k] = v
    
    return json.dumps(A)
    
    
def step_6():
    files = glob.glob('data/PairAuthors2csv_split/pair_processed_*')
    N = len(files)
    
    to_concat = []
    prev = pd.read_csv(files[0], header=None, sep='\t')
    for i in tqdm.tqdm(range(1, N), total=N):
        current = pd.read_csv(files[i], header=None, sep='\t')
        
        if prev.iloc[-1,0] == current.iloc[0,0]:
            current.iloc[0, 1] = join_dicts(current.iloc[0, 1], prev.iloc[-1, 1])
            
            prev = prev[:-1]
        
        prev.to_csv('data/PairAuthors2csv_split/pair_processed_join_%50d' % (i-1), header=None, sep='\t')
        del prev
        prev = current
    
    prev.to_csv('data/PairAuthors2csv_split/pair_processed_join_%50d' % (N-1), header=None, sep='\t')
    
    
    
if __name__ == '__main__':
#     step_1()
    step_3()
#     step_4()
#      step_5()
#     step_6()
    
#     total = len(mapped)
#     i = 2
# #     union_author_infos = mapped[0][0]
#     union_pair_authors = mapped[0][1]
#     for a, b in mapped[1:]:
#         print("%d of %d" % (i, total))
#         i += 1
# #         union_dict_infos(union_author_infos, a)
#         union_dict_pairs(union_pair_authors, b)
    
#     with open('data/pair_authors_processed_part1.txt', 'w') as outfile:
#         json.dump(union_pair_authors, outfile)



#     pool = multiprocessing.Pool(16)
#     mapped = pool.map(partial(work, valid_list), files_input[40:])
#     pool.close()
    
#     total = len(mapped)
#     i = 2
#     union_pair_authors = mapped[0][1]
#     for a, b in mapped[1:]:
#         print("%d of %d" % (i, total))
#         i += 1
#         union_dict_pairs(union_pair_authors, b)
    
#     with open('data/pair_authors_processed_part2.txt', 'w') as outfile:
#         json.dump(union_pair_authors, outfile)



#     p1 = json.load(open('data/pair_authors_processed_part1.txt'))
#     p2 = json.load(open('data/pair_authors_processed_part2.txt'))
#     union_dict_pairs(p1, p2)
#     with open('data/pair_authors_processed.txt', 'w') as outfile:
#         json.dump(p1, outfile)
