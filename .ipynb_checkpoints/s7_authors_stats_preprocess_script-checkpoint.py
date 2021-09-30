import glob, json, tqdm
import numpy as np
import pandas as pd
import s4_authors_stats as s4
import dask.dataframe as dd
import matplotlib.pyplot as plt
from scipy.stats import rankdata
from scipy.stats import pearsonr, spearmanr
from matplotlib.colors import LogNorm

from collections import defaultdict
from functools import partial
from multiprocessing import Pool
from tqdm.contrib.concurrent import process_map

plt.rcParams["axes.prop_cycle"] = plt.cycler("color", plt.cm.tab20.colors)
NCOLS = 4
SUFFIX = 2020
SUFFIX_STR = '_%d' % SUFFIX

header = '/mnt/e/MAG/mag-2021-01-05/advanced/'
fields_infos = 'FieldsOfStudy.txt'
fos_infos = pd.read_csv(header+fields_infos, header=None, sep='\t')[[0, 1, 2]]
fos_infos.columns = ['field_id', 'rank', 'normalized_name']


def to_process_papers(file):
    papers_fos_dict = defaultdict(lambda:set())
    papers_per_fos = dd.read_csv(file, header=None)[[1, 6]]
    papers_per_fos.columns = ['paper_id', 'parents_id']
    papers_per_fos = papers_per_fos.dropna()
    for idx,row in papers_per_fos.iterrows():
        for fos in row['parents_id'].split(','):
            papers_fos_dict[int(fos)].add(int(row['paper_id']))
    
    import pickle
    papers_fos_dict = dict(papers_fos_dict)
    with open(file.replace('paper', '1papers_per_fos'), 'wb') as handle:
        pickle.dump(papers_fos_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return papers_fos_dict


if __name__ == '__main__':
#     from s4_authors_stats import _step_1

#     authors_complete = dd.read_csv('data/AuthorsMetrics_split/authors_metrics_full_%d' % SUFFIX, sep='\t', header=None)
#     authors_complete.columns = ['author_id', 'cits', 'birth_year', 'citation_count', 'weights', 'fos']

#     def sum_cits(row):
#         c = sum(json.loads(row['citation_count']))
#         return c

#     authors_complete = authors_complete[authors_complete.apply(sum_cits, meta=(int), axis=1) > 0]
#     print(authors_complete.head())
    
    files = glob.glob('data_temp/FOS_split/fields_papers_*.csv')
    

    output_maps = process_map(to_process_papers, files, max_workers=16)
    final_maps = defaultdict(set, output_maps[0])
    for i in range(1, len(output_maps)):
        m = output_maps[i]
        for k, v in m.items():
            final_maps[k] = final_maps[k] | v
        output_maps[i] = {}
        
    for k, v in final_maps.items():
        print(k, len(v))