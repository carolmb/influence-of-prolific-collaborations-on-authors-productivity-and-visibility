import ast, csv
import glob, json
import dask, tqdm
import numpy as np
import pandas as pd
from dask import dataframe as dd
from collections import defaultdict
import multiprocessing
from functools import partial
from dask.diagnostics import ProgressBar

# import dask
# dask.config.set({'temporary_directory': '/data_temp'})
    
def _step_1(file, idx):
    chunk = dd.read_csv(file, header=None, 
                         names=['paper_id', 'field_id', 'score', 'field', 'parents', 'parents_id'])

    fields = ''
    current_reference = -1
    output = open("data/PaperFields_split/paper_fields_%d.csv" % idx, 'w')
    for idx,row in tqdm.tqdm(chunk.iterrows()):
        if current_reference == row['paper_id']:
            fields += ',(' + str(row['parents_id']) + ')'
        else:
            if current_reference != -1:
                output.write("%d\t%s\n" % (current_reference, fields))
            current_reference = row['paper_id']
            fields = '(' + str(row['parents_id']) + ')'

    if len(fields) > 0:
        output.write("%d\t%s\n" % (current_reference, fields))
            
    output.close()


def step_1():
    files = sorted(glob.glob('data_temp/FOS_split/fields_papers_*.csv'))
    f_inputs = list(zip(files, np.arange(len(files))))

    with multiprocessing.Pool(16) as pool:
            tqdm.tqdm(pool.starmap(_step_1, f_inputs), total=len(f_inputs))
                  

def step_2():
    files = sorted(glob.glob('data/PaperFields_split/*'), key=lambda x: int(x.split('_')[-1][:-4]))
    
    
    panda_concat_final = pd.read_csv(files[0], header=None, index_col=False,
                            sep='\t', names=['paper_id', 'parends_id'])
      
    to_save = []
    for file in tqdm.tqdm(files[1:]):
        
        last_id = panda_concat_final.iloc[-1, 0]
        last_refs = panda_concat_final[panda_concat_final['paper_id'] == last_id]['parends_id']
        n_authors = len(last_refs)


        panda_processed_i1 = pd.read_csv(file, header=None, index_col=False,
                            sep='\t', names=['paper_id', 'parends_id'])
        first_id = panda_processed_i1.iloc[0, 0]

        if last_id == first_id:
            new_authors = panda_processed_i1.iloc[0, 1] + ',' + last_refs
            panda_processed_i1.iloc[0, 1] = new_authors
            panda_concat_final = panda_concat_final[:-1]

        to_save.append(dd.from_pandas(panda_concat_final, npartitions=10))
        del panda_concat_final
        panda_concat_final = panda_processed_i1
        
        
    all_to_save = dd.concat(to_save)
    all_to_save.to_csv('data/papers_fos_parents.csv', header=None, index=None, sep='\t', single_file=True)
    

def _step_3(row):
        
    try:
        parents_id = ast.literal_eval(('[' + row['parents_id'] + ']'))
    except:
        if row['parents_id'] == None:
            parents_id = ''
        else:
            parents_id = ast.literal_eval(('[' + row['parents_id'].replace('nan', '-1') + ']'))
            parents_id.remove(-1)
        
    p_dict = defaultdict(lambda:0)
    for p in parents_id:
        if type(p) == type(1):
            p_dict[p] += 1
        else:
            for p0 in p:
                p_dict[p0] += 1/len(p)
    for k in p_dict:
        p_dict[k] = p_dict[k]/len(parents_id)

    row['parents_id'] = json.dumps(p_dict)
    return row
            
def step_3():
    # 8h running
    papers_fos = dd.read_csv('data/papers_fos_parents.csv', sep='\t', header=None, names=['paper_id', 'parents_id'])

    res = papers_fos.apply(_step_3, axis=1, meta=papers_fos)
    print(res.head())
    
    from dask.diagnostics import ProgressBar
    with ProgressBar():
        res.to_csv('data/PaperFOS_split/paper_fos_dict*.csv', header=None, index=None, sep='\t')
            

def json_simplify(row):
    s = row['weights']
    s = json.loads(s)
    ks = []
    vs = []
    for k, v in s.items():
        ks.append(str(int(k)))
        vs.append("%.4f" % v)
    
    row['weights'] = "%s %s" % (','.join(ks), ','.join(vs))
    return row
    

def step_4():
    # authors fields of study
    papers_authors = dd.read_csv('data/paper_authors.csv', sep='\t', header=None, names=['paper_id', 'authors_id'], dtype={'paper_id':'int'})
    with ProgressBar():
        papers_authors = papers_authors.set_index('paper_id', sorted=True)
    print(papers_authors.head())
    
    
    
    papers_fos = dd.read_csv('data/PaperFOS_split/*', sep='\t', header=None, 
                            names=['paper_id', 'weights'], dtype={'paper_id':'int'})
    with ProgressBar():
        papers_fos = papers_fos.set_index('paper_id', sorted=True)
    print(papers_fos.head())
    
    # merge: paper complete infos AND PaperFOS_split/paper_fos_dict*
    # iterar pelo dd gerado e somar os dicionárioss
    authors_fos = papers_authors.merge(papers_fos, on='paper_id')
#     authors_fos = authors_fos.apply(json_simplify, axis=1, meta=authors_fos)
    
    with ProgressBar():
        authors_fos.to_csv('data/AuthorsFOS_split/authors_fos_*.csv', sep='\t', header=None)
    

def step_4_5():
    # rm authors_fos_year_*
    papers_authors = dd.read_csv('data/AuthorsFOS_split/authors_fos_*.csv', sep='\t', header=None, names=['paper_id', 'authors_id', 'fields'], dtype={'paper_id':'int'})
    
    with ProgressBar():
        papers_authors = papers_authors.set_index('paper_id')
    
    with ProgressBar():
        papers = dd.read_csv('data/paper_complete_infos.csv', sep='\t', header=None, names=['paper_id', 'doi', 'year', 'authors', 'total_cits', 'cits'], dtype={'paper_id':'int'}).set_index('paper_id', sorted=True)
    
    j1 = papers_authors.merge(papers, how='left', on='paper_id')
    
    with ProgressBar():
        j1[['authors_id', 'fields', 'year']].to_csv('data/AuthorsFOS_split/authors_fos_year_*.csv', sep='\t', header=None)
        

def _step_5(maxyear, file):
        chunk = pd.read_csv(file, sep='\t', header=None, names=['paper_id', 'authors_id', 'fields', 'year'])
        authors_hist = dict()
        for _,row in chunk.iterrows():
            if float(row['year']) > maxyear:
                continue
            if row['fields'] is None or len(row['fields']) <= 1:
                continue
            fields = json.loads(row['fields'])
            if type(fields) == type(0.1):
                print(row['paper_id'])
                continue
            
            authors = row['authors_id'].split(',')
            for a in authors:
                if a in authors_hist:
                    for k,v in fields.items():
                        authors_hist[a][k] += v
                else:
                    authors_hist[a] = defaultdict(lambda:0, fields)

        idx = file.split('_')[-1]
        out = open('data/AuthorsFOS_split/authors_weights_year_%d_%s' % (maxyear,idx), 'w')
        for k,v in authors_hist.items():
            out.write("%s\t%s\n" % (k, json.dumps(v)))
        out.close()
            
        del authors_hist
    
    
def step_5():
    files = glob.glob('data/AuthorsFOS_split/authors_fos_year_*.csv')
    N = len(files)
    print(N)
    # só feito par 1960s e 1970
    for maxyear in range(1960, 2021, 10):
        from tqdm.contrib.concurrent import process_map
        process_map(partial(_step_5, maxyear), files, max_workers=16)
    
    
def step_6():
    # cat all files
    # sort authors_weights_complete by AuthorID
    pass


def join_weights(rows):
    W = defaultdict(lambda:0, json.loads(rows.at(0)['weights']))
    for row in rows[1:]:
        r = json.loads(row['weights'])
        for k,v in r.items():
            W[k] += v
    return json.dumps(W)
    

def _step_7(file):
    chunk = pd.read_csv(file, sep='\t', header=None, names=['author_id', 'weights']) # _complete_short_
#     out = open('data/AuthorsFOS_split/authors_weights_complete_year_%s' % file.split('_')[-2], 'w')
    out = open('data/AuthorsFOS_split/authors_weights_year_2020_weights_process_%s' % file.split('_')[-1], 'w')
    current = chunk.iloc[0,0]
    weights = defaultdict(lambda:0)
    for idx, row in chunk.iterrows():
        if current == row['author_id']:
            w = json.loads(row['weights'])
            for k, v in w.items():
                weights[k] += v
        else:
            out.write("%s\t%s\n" % (current, json.dumps(weights)))
            current = row['author_id']
            weights = defaultdict(lambda:0, json.loads(row['weights']))
    
    out.write("%s\t%s\n" % (current, json.dumps(weights)))
    out.close()
    del chunk
    
    
def step_7():
#     files = glob.glob('data/authors_weights_year_*_sorted.csv')
#     for file in files:
#         _step_7(file)
    
#     files = glob.glob('data/AuthorsFOS_split/authors_weights_final_*')
    files = glob.glob('data/AuthorsFOS_split/authors_weightes_year_2020_split_sorted_*')
    print(files[:3])
    from tqdm.contrib.concurrent import process_map
    process_map(_step_7, files, max_workers=10)



def merge_weights(w1, w2):
    w1 = json.loads(w1)
    w2 = json.loads(w2)
    for k,v in w2.items():
        if k in w1:
            w1[k] += v
        else:
            w1[k] = v
    return json.dumps(w1)


def step_8():
    files = sorted(glob.glob('data/AuthorsFOS_split/authors_weights_year_2020_weights_proces*'))
    
    N = len(files)
    
    to_join = []
    last_chunk = pd.read_csv(files[0], sep='\t', header=None, names=['author_id', 'weights'])
    
    for i in tqdm.tqdm(range(1, N), total=N):
        last_idx = last_chunk.iloc[-1,0]
        current_chunk = pd.read_csv(files[i], sep='\t', header=None, names=['author_id', 'weights'])
        current_idx = current_chunk.iloc[0,0]
        if last_idx == current_idx:
            last_row = last_chunk.iloc[-1,1]
            current_chunk.iloc[0,1] = merge_weights(current_chunk.iloc[0,1], last_row)
            last_chunk = last_chunk[:-1]
        
        last_chunk.to_csv('data/AuthorsFOS_split/authors_fos_weights_2020_final_%05d' % (i-1), sep='\t', header=None)
        del last_chunk
        last_chunk = current_chunk
    last_chunk.to_csv('data/AuthorsFOS_split/authors_fos_weights_2020_final_%05d' % i, sep='\t', header=None, index=None)

    
    
if __name__ == '__main__':
#     step_3()
#     step_4()
#     step_4_5()
#     step_5()
#     step_7()
    step_8()
