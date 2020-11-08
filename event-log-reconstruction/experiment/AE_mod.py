# coding: utf-8

# This is the implementation of [**Autoencoder**](http://www.iro.umontreal.ca/~lisa/bib/pub_subject/language/pointeurs/bengio+lecun-chapter2007.pdf)

# **Outline:**
# - Build model and loss function
# - Train model
# - Observe valdidate
# - Test

# **To do:**
# - Hyperparameter tuning
#     + lr
#     + layer1, layer2
#     + betas

# **Modification**
# - Weight initialization with xavier uniform
# - Adam optimization
# - LR decay


import argparse
import os
import pickle
import sys
import time
import numpy as np
import numpy
import pandas as pd
import torch
import torch.nn.functional as F
import torch.optim as optim
import torch.optim.lr_scheduler
import torch.utils.data
from torch.autograd import Variable
from torchvision import transforms

from utils.models import AE, AE_tanh, AE_dropout
from utils.utils import getDfWithTime, convert2df, getSubmission, fixTime, evaluation, getnanindex

sys.path.insert(0, './../utils')
from models import *

# Define parser
# name = "small_bpi"
name = 'bpi_2012'
# name = 'bpi_2013'
# name = 'small_log'
#name = 'large_log'

parser = {
    'train': True,
    'test': True,
    'model_class': 'AE',  # AE/AE_tanh
    'model_name': '',
    'data_dir': '../data/',
    'data_file': name + '.csv',
    'nan_pct': 0.3,
    'input_dir': '../input/{}/'.format(name),
    'batch_size': 16,
    'epochs': 1,
    'no_cuda': False,
    'seed': 7,
    'layer1': 50,
    'layer2': 20,
    'lr': 0.001,
    'betas': (0.9, 0.999),
    'lr_decay': 0.99,
}

args = argparse.Namespace(**parser)
args.output_dir = '/home/geovanni/Documents/TCC/WIP/event-log-reconstruction/output/{0}_{1}_{2}/'.format(name, args.nan_pct, args.model_class)
print(args.output_dir)
if not os.path.isdir(args.output_dir):
    os.makedirs(args.output_dir)

args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)

kwargs = {'num_workers': 2, 'pin_memory': True} if args.cuda else {}

preprocessed_data_name = os.path.join(args.input_dir, 'preprocessed_data_{}.pkl'.format(args.nan_pct))
with open(preprocessed_data_name, 'rb') as f:
    min_max_storage = pickle.load(f)
    complete_matrix_w_normalized_time_train = pickle.load(f)
    missing_matrix_w_normalized_time_train = pickle.load(f)
    avai_matrix_train = pickle.load(f)
    nan_matrix_train = pickle.load(f)
    complete_matrix_w_normalized_time_val = pickle.load(f)
    missing_matrix_w_normalized_time_val = pickle.load(f)
    avai_matrix_val = pickle.load(f)
    nan_matrix_val = pickle.load(f)
    pad_matrix_val = pickle.load(f)
    complete_matrix_w_normalized_time_test = pickle.load(f)
    missing_matrix_w_normalized_time_test = pickle.load(f)
    avai_matrix_test = pickle.load(f)
    nan_matrix_test = pickle.load(f)
    pad_matrix_test = pickle.load(f)
    cols_w_time = pickle.load(f)
    cols_w_normalized_time = pickle.load(f)

file_name = os.path.join(args.input_dir, 'parameters_{}.pkl'.format(args.nan_pct))
with open(file_name, 'rb') as f:
    most_frequent_activity = pickle.load(f)
    first_timestamp = pickle.load(f)
    avai_instance = pickle.load(f)
    nan_instance = pickle.load(f)
    train_size = pickle.load(f)
    val_size = pickle.load(f)
    test_size = pickle.load(f)
    train_row_num = pickle.load(f)
    val_row_num = pickle.load(f)
    test_row_num = pickle.load(f)

# # Load data

# ## Train


complete_matrix_w_normalized_time_trainLoader = torch.utils.data.DataLoader(complete_matrix_w_normalized_time_train,batch_size=16, shuffle=True, num_workers=2)

complete_matrix_w_normalized_time_trainLoader.transform = transforms.Compose([transforms.ToTensor()])

missing_matrix_w_normalized_time_trainLoader = torch.utils.data.DataLoader(missing_matrix_w_normalized_time_train,
                                                                           batch_size=16, shuffle=True, num_workers=2)
missing_matrix_w_normalized_time_trainLoader.transform = transforms.Compose([transforms.ToTensor()])

avai_matrix_trainLoader = torch.utils.data.DataLoader(avai_matrix_train, batch_size=16, shuffle=True, num_workers=2)
avai_matrix_trainLoader.transform = transforms.Compose([transforms.ToTensor()])

normalized_complete_df_name = os.path.join(args.input_dir, 'normalized_complete_df_{}.csv'.format(args.nan_pct))
normalized_complete_df = pd.read_csv(normalized_complete_df_name)

normalized_missing_df_name = os.path.join(args.input_dir, 'normalized_missing_df_{}.csv'.format(args.nan_pct))
normalized_missing_df = pd.read_csv(normalized_missing_df_name)

missing_true_val = normalized_missing_df[train_row_num:-test_row_num].reset_index(drop=True)
complete_true_val = normalized_complete_df[train_row_num:-test_row_num].reset_index(drop=True)

missing_true_test = normalized_missing_df[-test_row_num:].reset_index(drop=True)
complete_true_test = normalized_complete_df[-test_row_num:].reset_index(drop=True)

missing_true_val.shape,missing_true_test.shape

nan_time_index_val, nan_activity_index_val = getnanindex(missing_true_val)

nan_time_index_test, nan_activity_index_test = getnanindex(missing_true_test)

pd.isnull(normalized_missing_df).sum()

pd.isnull(missing_true_val).sum()

pd.isnull(missing_true_test).sum()
#fix nulls /\


if args.model_class == 'AE':
    model = AE(complete_matrix_w_normalized_time_train.shape, args.layer1, args.layer2)

if args.model_class == 'AE_tanh':
    model = AE_tanh(complete_matrix_w_normalized_time_train.shape, args.layer1, args.layer2)

if args.model_class == 'AE_dropout':
    model = AE_dropout(complete_matrix_w_normalized_time_train.shape, args.layer1, args.layer2)

if args.cuda:
    model.cuda()

model


# ## Define loss


# Define loss
def loss_function(recon_x, x, avai_mask):
    BCE = F.binary_cross_entropy(recon_x, x, weight=avai_mask, size_average=False)
    return BCE


optimizer = optim.Adam(model.parameters(), lr=args.lr, betas=args.betas)

# Adjust learning rate per epoch: http://pytorch.org/docs/master/optim.html?highlight=lr_scheduler#torch.optim.lr_scheduler.LambdaLR

# Method 1:
lambda1 = lambda epoch: args.lr_decay ** epoch
scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=[lambda1])


# Method 2:
# scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=10)


# ## Utils


def save_model(model, epoch, score):
    model_file = os.path.join(args.output_dir,
                              'model_{}_epoch{}_score{:.4f}.pth'.format(args.model_class, epoch, score))
    torch.save(model.state_dict(), model_file)


def load_model(model, model_name):
    model_file = os.path.join(args.output_dir, model_name)
    assert os.path.isfile(model_file), 'Error: no model found!'
    model_state = torch.load(model_file)
    model.load_state_dict(model_state)


def val(model, missing_matrix_w_normalized_time_val, complete_matrix_w_normalized_time_val, avai_matrix_val):
    model.eval()
    m_val = missing_matrix_w_normalized_time_val
    #m_val = Variable(torch.Tensor(m_val).float())
    m_val = torch.from_numpy(numpy.array(m_val, dtype='float32'))
    c_val = complete_matrix_w_normalized_time_val
    #c_val = Variable(torch.Tensor(c_val).float())
    c_val = torch.from_numpy(numpy.array(c_val, dtype='float32'))

    #avai_matrix_val = Variable(torch.Tensor(avai_matrix_val).float())
    avai_matrix_val = torch.from_numpy(numpy.array(avai_matrix_val, dtype='float32'))
    if args.cuda:
        m_val = m_val.cuda()
        c_val = c_val.cuda()
        avai_matrix_val = avai_matrix_val.cuda()

    recon_val = model(m_val)
    val_loss = loss_function(recon_val, c_val, avai_matrix_val)

    #return val_loss.data[0] / len(c_val.data)
    return val_loss.data / len(c_val.data)


missing_true_val.head()

complete_true_val.head()


# # Train model

def train(epoch, model, optimizer):
    model.train()
    train_loss = 0

    zips = zip(missing_matrix_w_normalized_time_trainLoader.dataset, complete_matrix_w_normalized_time_trainLoader.dataset, avai_matrix_trainLoader.dataset)
    enums = enumerate(zips)
    for batch_idx, (m_data, c_data, avai_mask)  in enums:

        #c_data = Variable(c_data)
        #m_data = Variable(m_data)
        #avai_mask = Variable(avai_mask)
        c_data = torch.from_numpy(numpy.array(c_data, dtype='float32'))
        m_data = torch.from_numpy(numpy.array(m_data, dtype='float32'))
        avai_mask = torch.from_numpy(numpy.array(avai_mask, dtype='float32'))

        if args.cuda:
            c_data = c_data.cuda()
            m_data = m_data.cuda()
            avai_mask = avai_mask.cuda()

        optimizer.zero_grad()

        recon_data = model(m_data)

        loss = loss_function(recon_data, c_data, avai_mask)

        loss.backward()
        train_loss += loss.data
        optimizer.step()

    return train_loss / len(complete_matrix_w_normalized_time_trainLoader.dataset)


if args.train:
    for epoch in range(1, args.epochs + 1):
        init = time.time()

        # method 1 scheduler
        scheduler.step()
        train_loss = train(epoch, model, optimizer)
        end_train = time.time()

        val_score = val(model, missing_matrix_w_normalized_time_val,
                        complete_matrix_w_normalized_time_val, avai_matrix_val)

        '''
        #save_model(model, epoch, val_score)
        if epoch == 1:
            current_best = val_score
            save_model(model, epoch, val_score)
        
        else:
            if val_score < current_best:
                current_best = val_score
                save_model(model, epoch, val_score)
        '''

        # method 2 scheduler
        # scheduler.step(val_score)

        end = time.time()
        print('====> Epoch {} | Train time: {:.4f} ms| End time: {:.4f} ms | Train loss: {:.4f} | Val score: {:.4f}'.
              format(epoch, (end_train - init) * 1000, (end - init) * 1000, train_loss, val_score))
else:
    load_model(model, args.model_name)

# # Predict and evaluate


if args.test:
    m_test = missing_matrix_w_normalized_time_test
    m_test = Variable(torch.Tensor(m_test).float())

    if args.cuda:
        m_test = m_test.cuda()

    print('Predicting...')
    recon_test = model(m_test)

    y = Variable(recon_test, requires_grad=True)
    y = y.cpu().detach()

    #numpy.savetxt('array_hf.csv', y.numpy(), delimiter=',')

    #your_file = open(args.output_dir + 'submission.csv', 'ab')
    #numpy.savetxt(X=)
    #print(args.output_dir + 'submission.csv')
    #numpy.savetxt(recon_test.numpy())
    #your_file.close()

    #recon_test.to_csv(args.output_dir + 'submission.csv', index=False)


    print('\n')
    print('Converting to dataframe...')
    recon_df_w_normalized_time = convert2df(y, pad_matrix_test, cols_w_normalized_time, test_row_num)

    print('Transforming Normalized Time to Time...')
    recon_df_w_time = getDfWithTime(recon_df_w_normalized_time, missing_true_test, min_max_storage)

    print('Getting submission...')
    submission_df = getSubmission(recon_df_w_normalized_time, missing_true_test, complete_true_test, first_timestamp)
    submission = fixTime(submission_df)

    print('Testing...')
    #mae_time, rmse_time, acc = evaluation(submission, nan_time_index_test, nan_activity_index_test, show=True)
    print('\n')

    print('Saving submission...')
    submission_df.to_csv(args.output_dir + 'submission.csv', index=False)
    print('Done!')

#submission_df.head(10)

#submission.head(10)