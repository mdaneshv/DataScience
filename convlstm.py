
import numpy as np
from sklearn import preprocessing
import pandas as pd
import matplotlib.pyplot as plt
from keras.models import Model, Sequential
from keras.layers import GRU, LSTM, Dense, Input, Activation, Dropout
from keras.layers.convolutional_recurrent import ConvLSTM2D
from keras import optimizers
from keras import backend as K
import seaborn as sns
import pandas.util.testing as tm


# Original data
Origin_data = np.genfromtxt('U16.dat', delimiter=' ')

# Define encoder-decoder
'''
def encoder_decoder(data, code_size):
  features = data.shape[1]
  m = data.shape[0]

  # normalize features to have zero mean and variance one
  for i in range(features):
        data[:, i] = preprocessing.scale(data[:, i])


  x_train = np.random.rand(m, features)  # deterministic values
  x_train_noisy = x_train + np.random.normal(size=(m, features)) # noisy values

  input_vector = Input(shape=(features,))
  code = Dense(code_size, activation='tanh')(input_vector)
  output = Dense(features, activation='tanh')(code)

  autoencoder = Model(input_vector, output)
  autoencoder.compile(optimizer='adam', loss='mse')
  autoencoder.fit(x_train_noisy, x_train, epochs=1)

  dataset = autoencoder.predict(data)  # denoise data

  return dataset
'''
# Create datasets for ConvLSTM2d
def ConvLSTM_dataset(dataset, time_window, rows, columns):
    features = dataset.shape[0] 
    m = dataset.shape[1] 
    samples = int(m / columns) - 1 # number of images 
    test_size = 5                  # the true test size for images will become: test_size - time_window
    train_size = samples - test_size
    

    # start converting dataset into 2D-images
    Z = np.zeros((samples, rows, columns))  
    for i in range(samples):
        Z[i, :, :] = dataset[:, i * columns:i * columns + columns] # We cut dataset into different parts: 2D-images

    image_data = np.transpose(Z)

    # Creating a sequence of data from 2D-images we have created above
    Znew = {}  
    for i in range(time_window):
        Znew[i] = image_data[:, :, i:samples - (time_window - i - 1)]

    X = Znew[0]
    for i in range(time_window - 1):
        X = np.vstack([X, Znew[i + 1]])

    X = np.transpose(X)
    Y = Z[time_window:, :, :]  # target values for X

    # creating train and test sets and corresponding target values from X and Y
    X_train = X[:train_size, :]
    Y_train = Y[:train_size, :]
    X_test = X[train_size:train_size + test_size, :]
    X_test = np.delete(X_test, (test_size - time_window), axis=0)
    Y_test = Y[train_size:train_size + test_size, :]

    # reshape input and output to be fed into ConvLastm2D layers: input must be 5 dimensional 
    Xtrain_set = X_train.reshape((X_train.shape[0], time_window, rows, columns, 1))
    Xtest_set = X_test.reshape((X_test.shape[0], time_window, rows, columns, 1))
    Ytrain_set = Y_train.reshape((Y_train.shape[0], rows, columns, 1))
    Ytest_set = Y_test.reshape((Y_test.shape[0], rows, columns, 1))

    return Xtrain_set, Ytrain_set, Xtest_set, Ytest_set

# Define ConvLSTM2D model
def create_ConvLSTM_layers(X, Y, filters, kernel_size, batch_size, epochs, learning_rate):
    time_window, rows, columns = np.shape(X)[1], np.shape(X)[2], np.shape(X)[3]

    model = Sequential()

    model.add(ConvLSTM2D(filters=filters, kernel_size=kernel_size,
                         input_shape=(time_window, rows, columns, 1),
                         padding='same', return_sequences=True))
    
    model.add(ConvLSTM2D(filters=filters, kernel_size=kernel_size,
                         input_shape=(time_window, rows, columns, 1),
                         padding='same', return_sequences=True))
  
    # last layer has 1 filter
    model.add(ConvLSTM2D(filters=1, kernel_size=kernel_size,    
                         input_shape=(time_window, rows, columns, 1),
                         padding='same', data_format='channels_last'))
    

    adam = optimizers.Adam(lr=learning_rate, beta_1=0.99, beta_2=0.999)

    model.compile(loss='mse', optimizer=adam #metrics=['accuracy'])

    # fit model to the data
    history = model.fit(X, Y, epochs=epochs, batch_size=batch_size, verbose=2, shuffle=True)

    return model, history


# sequence to sequence predictions
def prediction(model, X, time_window, rows, columns):  

    time_window, rows, columns = np.shape(X)[1], np.shape(X)[2], np.shape(X)[3]

    Predictions = np.zeros((X.shape[0], rows, columns, 1))

    first_sequence = X[0, :, :, :, :].reshape((1, time_window, rows, columns, 1))
    Predictions[0, :, :, :] = model.predict(first_sequence)

    for i in range(1, X.shape[0]):
        if i < time_window:
            ith_sequence = X[i, :, :, :, :].reshape((1, time_window, rows, columns, 1))
            ith_sequence[0, (time_window - i):time_window, :, :, :] = Predictions[:i, :, :, :]
            Predictions[i, :, :, :] = model.predict(ith_sequence)
        else:
            ith_sequence = Predictions[i - time_window:i, :, :, :].reshape((1, time_window, rows, columns, 1))
            Predictions[i, :, :, :] = model.predict(ith_sequence)

    return Predictions

# Paste columns of Predictions and true values to create 2 vectors for plotting
def make_plots(Predictions, Ytest_set, pred_steps):
    Ypred = {}
    Ytest = {}

    for i in range(rows):
        Ypred[i] = Predictions[0, i, :, 0]
        Ytest[i] = Ytest_set[0, i, :, 0]
        for j in range(0, pred_steps):
            Ypred[i] = np.append(Ypred[i], Predictions[j, i, :, 0])
            Ytest[i] = np.append(Ytest[i], Ytest_set[j, i, :, 0])

    # plots  
    for i in range(rows):
        plot1, = plt.plot(Ytest[i])

        plot2, = plt.plot(Ypred[i])

        plt.xlabel('steps')

        plt.ylabel('$X[%i]$' % i)

        plt.title('Prediction for feature $%i$' % i, fontsize=10)

        plt.legend([plot1, plot2], ["true_values", "prediction"])

        plt.savefig('predction for %i' % i)

        plt.show()

    return Ypred, Ytest, plot1, plot2


time_window = 2  # recurrent steps or tiem-steps
rows = 16        # I chose it to be the same as number of features
columns = 3      # columns of images 
pred_steps = 3   # prediction horizon shown on x_axis of plots which is : pred_steps * columns 
# pred_steps < test_seize - time_window
filters = 30     # number of filters in convolutional layres
kernel_size = (10,3)
batch_size = 128
epochs = 7
learning_rate = 0.003
code_size = 10   # number of hidden units in encoder-decoder

#dataset = encoder_decoder(np.transpose(Origin_data), code_size)
Xtrain_set, Ytrain_set, Xtest_set, Ytest_set = ConvLSTM_dataset(Origin_data, time_window, rows, columns)
model, history = create_ConvLSTM_layers(Xtrain_set, Ytrain_set, filters, kernel_size, batch_size, epochs, learning_rate)
Predictions = prediction(model, Xtest_set, time_window, rows, columns)
Ypred, Ytest, plot1, plot2 = make_plots(Predictions, Ytest_set, pred_steps)

