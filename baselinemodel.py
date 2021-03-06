import tensorflow as tf
import numpy as np
import nltk.data
import pandas as pd
import math
import re
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.model_selection import train_test_split, KFold
from preprocess import loadDataset
from word2vec_training import loadWord2VecConvertedFromGlove, loadWord2VecOnGoogleDataset

# Parameters
learning_rate = 0.001
epochs = 40
batch_size = 32
hidden_nodes = 128
dropout = 0.2
split_size = 10

# Tensorflow Graph
x = tf.placeholder(shape = ([None, 600]), dtype = tf.float64, name = 'x')
y = tf.placeholder(shape = [None, 4], dtype = tf.float64, name = 'y')

# Weights
weights = {
        'W1': tf.get_variable("W1", shape = [600, hidden_nodes], 
                              dtype = tf.float64, initializer = tf.contrib.layers.xavier_initializer()),
 
        'W2': tf.get_variable("W2", shape = [hidden_nodes, 4], 
                              dtype = tf.float64, initializer = tf.contrib.layers.xavier_initializer()) 
}

#Biases
biases = {
        'b1': tf.get_variable("b1", shape = [1, hidden_nodes], 
                              dtype = tf.float64, initializer = tf.constant_initializer(0)),
                              
        'b2': tf.get_variable("b2", shape = [1, 4], 
                              dtype = tf.float64, initializer = tf.constant_initializer(0))
}

# Feedforward neural network model
def forward_propagation(X):
    hidden_layer = tf.matmul(X, weights['W1']) + biases['b1']
    hidden_layer = tf.nn.relu(hidden_layer)
    hidden_layer_dropout = tf.nn.dropout(hidden_layer, keep_prob = (1 - dropout))
    out_layer = tf.matmul(hidden_layer_dropout, weights['W2']) + biases['b2']
    
    return out_layer

# Construct the model
y_hat = forward_propagation(x)

class_weights = tf.constant([[0.3, 0.3, 0.3, 0.1]], dtype=tf.float64)
w = tf.reduce_sum(class_weights * y, axis=1)
unweighted_losses = tf.nn.softmax_cross_entropy_with_logits_v2(labels=y, logits=y_hat)
weighted_losses = unweighted_losses * w
cost = tf.reduce_mean(weighted_losses)
#cost = tf.reduce_mean(tf.losses.softmax_cross_entropy(logits = y_hat, onehot_labels = y, weights=class_weights))

# Cost and optimizer functions
#cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits = y_hat, labels = y))
optimizer = tf.train.AdamOptimizer(learning_rate = learning_rate).minimize(cost)

# Accuracy function
correct_predicton = tf.equal(tf.argmax(y, 1), tf.argmax(y_hat, 1))
accuracy = tf.reduce_mean(tf.cast(correct_predicton, tf.float64))

# Initializing the variables
init = tf.global_variables_initializer()

def clean(s):
    return " ".join(re.findall(r'\w+', s, flags = re.UNICODE)).lower()

print("Loading word2vec model...")
word2vec_model = loadWord2VecConvertedFromGlove()
print("Finished loading word2vec model.")
    
def prepare_dataset(bodiesfile, stancesfile):
    #print("Loading word2vec model...")
    #word2vec_model = loadWord2VecConvertedFromGlove()
    #word2vec_model = loadWord2VecOnGoogleDataset()
    #print("Finished loading word2vec model.")
    
    print("Getting dataset...")
    headline_body_pairs, stances = loadDataset(bodiesfile, stancesfile);
    print("Finished getting dataset.")
    
    stance_labelencoder = LabelEncoder()
    stances_label_encoded = stance_labelencoder.fit_transform(stances)
    stances_label_encoded = stances_label_encoded.reshape(len(stances_label_encoded), 1)
    onehotencoder = OneHotEncoder(sparse = False)
    stances_onehotencoded = onehotencoder.fit_transform(stances_label_encoded)

    headline_body_pairs_vec = [None] * len(headline_body_pairs)
    
    for i in range(0,  len(headline_body_pairs)):
        
        # getting the headline and body separately
        headline = headline_body_pairs[i][0]
        body = headline_body_pairs[i][1]

        # cleaning the headline and body
        headline = clean(headline)
        body = clean(body)
        
         # tokenizing of headline and body    
        headline = nltk.word_tokenize(headline)
        body = nltk.word_tokenize(body)
        
        # getting word vectors, replacing unknown words and numbers with zero vectors
        headline_vec = np.array([np.array(word2vec_model[word]) if word in word2vec_model.vocab else np.zeros((300,)) for word in headline])
        body_vec = np.array([np.array(word2vec_model[word]) if word in word2vec_model.vocab else np.zeros((300,)) for word in body])
        
        # columnwise mean
        headlinevec_mean = np.mean(np.array(headline_vec), axis=0)
        bodyvec_mean = np.mean(np.array(body_vec), axis=0)
        
        # concatenating the headline and body vectors
        headline_body_pairs_vec[i] = np.concatenate((headlinevec_mean, bodyvec_mean),axis=0)
        
    headline_body_pairs_vec = np.array(headline_body_pairs_vec)
    
    return headline_body_pairs_vec, stances_onehotencoded

def split_dataset(x, y):
    X_train, X_dev, y_train, y_dev = train_test_split(x, y, test_size = 0.1, random_state = 42)
    return X_train, X_dev, y_train, y_dev

def train(session, X_train, y_train):
    # Configure GPU not to use all memory
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
        
    session.run(init)
    print("\n")
    total_batch = int(math.ceil(len(X_train)/batch_size))
    for epoch in range(epochs):
        avg_cost = 0
        loss = 0
        start, end = 0, batch_size
        for i in range(total_batch):
            batch_x = X_train[start:end]
            batch_y = y_train[start:end]
            
            _, loss = session.run([optimizer, cost], feed_dict = {x: batch_x, y: batch_y})
            avg_cost += loss
            start += batch_size
            if i == total_batch - 2:
                end = len(X_train)
            else:
                end += batch_size
        avg_cost = avg_cost/total_batch
        train_accuracy = session.run(accuracy, feed_dict = {x: X_train, y: y_train})
        print("Epoch:", (epoch + 1), "cost =", "{:.3f}".format(avg_cost), "accuracy =", "{:.3f}".format(train_accuracy))
   
def cross_validate(session, X_train, X_dev, X_test, y_train, y_dev, y_test):
    results = []
    kf = KFold(n_splits = split_size)
    for train_idx, val_idx in kf.split(X_train, y_train):
        train_x = X_train[train_idx]
        train_y = y_train[train_idx]
        val_x = X_train[val_idx]
        val_y = y_train[val_idx]
        train(session, train_x, train_y)
        results.append(session.run(accuracy, feed_dict={x: val_x, y: val_y}))
    dev_accuracy = session.run(accuracy, feed_dict={x: X_dev, y: y_dev})
    test_accuracy = session.run(accuracy, feed_dict={x: X_test, y: y_test})
    return results, dev_accuracy, test_accuracy

def train_only(session, X_train, X_dev, X_test, y_train, y_dev, y_test):
    # Configure GPU not to use all memory
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
        
    session.run(init)
    print("\n")
    total_batch = int(math.ceil(len(X_train)/batch_size))
    for epoch in range(epochs):
        avg_cost = 0
        loss = 0
        start, end = 0, batch_size
        for i in range(total_batch):
            batch_x = X_train[start:end]
            batch_y = y_train[start:end]
            
            _, loss = session.run([optimizer, cost], feed_dict = {x: batch_x, y: batch_y})
            avg_cost += loss
            start += batch_size
            if i == total_batch - 2:
                end = len(X_train)
            else:
                end += batch_size
        avg_cost = avg_cost/total_batch
        trainy_hat, train_accuracy = session.run([y_hat,accuracy], feed_dict = {x: X_train, y: y_train})
        #trainy_hat = session.run( tf.Print(trainy_hat,[trainy_hat]))
        #print(trainy_hat)
        print("Epoch:", (epoch + 1), "cost =", "{:.3f}".format(avg_cost), "accuracy =", "{:.3f}".format(train_accuracy))
    dev_predictions, dev_accuracy = session.run([y_hat,accuracy], feed_dict={x: X_dev, y: y_dev})
    test_predictions, test_accuracy = session.run([y_hat, accuracy], feed_dict = {x: X_test, y: y_test})
    return dev_accuracy, test_predictions, test_accuracy , dev_predictions 
   
def main():
    X_train, y_train = prepare_dataset('./dataset/train_bodies1.csv','./dataset/train_stances1.csv')
    X_dev, y_dev = prepare_dataset('./dataset/dev_bodies1.csv','./dataset/dev_stances1.csv')
    X_test, y_test = prepare_dataset('./dataset/competition_test_bodies.csv','./dataset/competition_test_stances.csv')
    #X_train, X_dev, y_train, y_dev = split_dataset(x, y)
    with tf.Session() as session:
        #train(session, X_train, y_train)
        #result, dev_accuracy, test_accuracy = cross_validate(session, X_train, X_dev, X_test, y_train, y_dev, y_test)
        dev_accuracy, test_predictions, test_accuracy, dev_predictions = train_only(session, X_train, X_dev, X_test, y_train, y_dev, y_test)
        
        test_preds = np.argmax(test_predictions, 1)
        dev_preds  = np.argmax(dev_predictions , 1)
        
        stances = test_preds.astype(str)
        stances_dev = dev_preds.astype(str)
        
        relation_map = {
                0:'agree',
                1:'disagree',
                2:'discuss',
                3:'unrelated',
        }
        for i in range(0, len(test_preds)):
            stances[i]=relation_map[test_preds[i]]
        for i in range(0, len(dev_preds)):
            stances_dev[i]=relation_map[dev_preds[i]]
        
        df = pd.read_csv('./dataset/competition_test_stances.csv')
        new_column = pd.DataFrame({'Stance': stances})
        df['Stance']=new_column
        
        df1 = pd.read_csv('./dataset/dev_stances1.csv')
        new_column_dev = pd.DataFrame({'Stance': stances_dev})
        df1['Stance']=new_column_dev
        
        df.to_csv('testset_res.csv',index=False)
        df1.to_csv('devset_res.csv',index=False)
        
        print("\n")
        #print("Cross-validation result: ", result)
        print("Dev accuracy: ", dev_accuracy)
        print("Test accuracy: ", test_accuracy)