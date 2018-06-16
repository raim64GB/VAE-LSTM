""" Prepare the data for creation of TFRecords """
from __future__ import absolute_import, division, print_function

import io
import os
from collections import Counter, defaultdict

import nltk
import numpy as np
from gensim.models import FastText as ft

# Additions of special characters for sequence generation. You may add your own...
PAD = "<PAD>"
START = "<START>"
EOS = "<EOS>"
UNK = "<UNK>"

# Path variables for reading in some of the data
WORD_VECS = os.getcwd() + "crawl-300d-2M.vec"
VOCAB = os.getcwd() + "vocab"

class Vocab():
    """ For reading data, processing for input, and writing to TFRecords
    """
    def __init__(self, train=False):
        self.embeddings, _, self.embedding_dim = self.read_embeddings(path=WORD_VECS) # map of ID to vecctor
        self.vocab = defaultdict(self.next_val) # maps tokens to ids. Autogenerate next id as needed
        self.reverse_vocab = {}
        self.token_counter = Counter() # counts token frequency
        self.train = train # Mode for training

        # Add special characters to the vocab
        self.vocab[PAD] = 0
        self.vocab[START] = 1
        self.vocab[EOS] = 2
        self.vocab[UNK] = 3
        self.next = 3 # after 2 is 3 and so on...

        # Reads created vocab from file if it exists
        if os.path.isfile(VOCAB):
            self.load_vocab(VOCAB)


    def next_val(self):
        self.next += 1
        return self.next

    def prep_seq(self, seq):
        """ Tokenizes/cleans and converts sequence of text to sequence of (chars or words)
        Args:
            seq: A sequence to to be prepared
        Returns:
            A list of IDs
        """

        seq = self.tokenize(seq)

        seq = self.map_to_ids(seq)

        # Add START and EOS tokens
        seq = [1] + seq
        seq = seq + [2]

        return seq

    def tokenize(self, seq):
        """ Tokenizes the input sequence.
        Args:
            seq: A sequence to be tokenized/cleaned(e.g "Hello, this is a sequence.")
        Returns: 
            A list of tokens(e.g words or charcters)
        """

        seq = seq.lower()

        return nltk.word_tokenize(seq)

    def map_to_ids(self, tok_seq):
        """ Maps a list of tokens to their respective ids
        Args:
            tok_seq: A sequence of tokens(words or chars)
        Returns:
            A list of IDs
        """

        return [self.tok_to_id(token) for token in tok_seq]

    def tok_to_id(self, token, oov_words=True):
        """ Maps a token to it's corresponding ID. Or if in training mode, also adds new words to the vocab
        Args:
            token: A word
            train: An option for training(updates the vocab). If train is set to False OOV words are mapped to UNK or a vector is created for the OOV word
            oov_words: An option when building vocab to map words without pretrained embeddings to UNK
        Returns:
            An ID
        """

        if self.train:
            if oov_words:
                # If there is exists an embedding for token
                if token in self.embeddings.keys():
                    self.token_counter[token] += 1
                    return self.vocab[token]
                else:
                    self.token_counter[UNK] += 1
                    return self.vocab[UNK]
            else:
                self.token_counter[token] += 1
                return self.vocab[token]       
        elif token in self.vocab:
            self.token_counter[token] += 1
            return self.vocab[token]
        else:
            self.token_counter[UNK] += 1
            return self.vocab[UNK]

    def make_reverse_vocab(self):
        """ Makes a reverse vocab for the given vocab.
        """
        self.reverse_vocab = {id_:token for token,id_ in self.vocab.items()}

    def ids_to_text(self, id_list):
        """ Maps a sequence of IDs to a string
        Args:
            id_list: A sequence of IDs
        Returns:
            text: A text string that is supposed to be a sentencentences: the list of split sentences.
        """

        tokens = ''.join(map(lambda x:self.reverse_vocab[x],id_list))

        return tokens

    def ids_to_string(self,tokens,length=None):
        """ Converts a text of ids(kind of like the output of the model) into a readable format with words.
        Args:
            tokens: A string comprised of tokens
            length: The length of the string you want it to tokenize
        Returns:
            string: The corresponding string for the ids with words in them
        """
        
        string = ''.join([self.reverse_vocab[x] for x in tokens[:length]])
        
        return string



    def create_embedding_matrix(self, path=None, all_embeddings=True, oov_embeddings=False):
        """ Reads the FastText word embeddings from a file, adds new embeddings to vocab, and fills in any word embeddings
        Args:
            path: path to the .vec file
            all_embeddings: An option to add all pretrained vectors to vocab. This will cause the model to be slower to train
            oov_embeddings: An option to generate embeddings for an OOV word
        Returns:
            embeddings: A numpy array of vectors
        """

        if path is None:
            raise Exception('You must specify a path to the pretrained embeddings...')

        if all_embeddings:
            for word in self.embeddings:
                self.vocab[word[0]] # add the token to the vocab


        print("Adding embeddings to the words in the vocab...")

        embedding_matrix = list()

        # Initialize special tokens
        embedding_matrix.append(np.zeros(self.embedding_dim).tolist()) # Adding the PAD embedding
        embedding_matrix.append(np.random.randn(self.embedding_dim).tolist()) # Adding the START embedding
        embedding_matrix.append(np.random.randn(self.embedding_dim).tolist()) # Adding the EOS embedding
        embedding_matrix.append(np.random.randn(self.embedding_dim).tolist()) # Adding the UNK embedding

        count = 0
        for word, id_ in enumerate(self.vocab.items()):
            if word in [PAD, UNK, START, EOS]:
                continue

            if word in self.embeddings.keys():
                # import the vector from the data dictionary
                embedding_matrix[id_] = self.embeddings[word]
            else:
                count += 1
                if oov_embeddings:
                    embedding_matrix.append(self.generate_embedding(word))

        print("There were %d words without pretrained vectors" % count)

        # Convert to numpy array
        embedding_matrix = np.array([np.array(i) for i in embedding_matrix])

        return embedding_matrix

    def read_embeddings(self, path):
        """ Reads word embeddings from file that are saved in the FastText format
        Args:
            path: Path to the embedding file
        Returns:
            embeddings: A dictionary of words to their corresponding vector
            length: The length of the word embedding
            dim: The dimension of the word embedding
        """

        print("Reading embeddings from:", path)

        fin = io.open(path, 'r', encoding='utf-8', newline='\n', errors='ignore')
        length, dim = map(int, fin.readline().split())

        data = {}
        for line in fin:
            tokens = line.rstrip().split(' ')
            data[tokens[0]] = map(float, tokens[1:])

        return data, length, dim

    def generate_embedding(self, word):
        """ Generates an embedding for an OOV word with FastText Pretrained model
        Args:
            word: The word to generate an embedding for
        Returns:
            vector: An 300 dimensional vector is returned
        """

        # Load the fattext format
        model = ft.load_fasttext_format(WORD_VECS)

        result = model.similar_by_word(word=word, topn=2)

        vector = np.mean(np.array([model[result[0]],model[result[1]]]), axis=0)

        vector = vector.tolist()

        return vector

    def save_vocab(self, path=None):
        """ Saves the vocabulary to file.
        """

        if path is None:
            print("No path for vocab specified. Saving to:", os.getcwd())

        print("Writing vocab to file...")

        with open(path, 'w') as writer:
            for word, id_ in self.vocab:
                writer.write(word + ' ' + str(id_) + '\n')

        print("Finished writing to vocab")

        return

    def load_vocab(self, path=None):
        """ Loads the vocab file from the specified path
        """

        if path is None:
            raise Exception("Error: A path must be specified!")

        print("Loading vocab at:", path)

        with open(path, 'r') as vocab_f:
            for i, line in enumerate(vocab_f):
                # skip rereading special chars
                if i < 3:
                    continue
                pieces = line.split()
                if len(pieces) != 2:
                    print("Line %d is formated incorrectly\n" % line)
                    continue
                word = pieces[0]
                if word in self.vocab:
                    raise Exception("Duplicate word %s found in vocab" % word)
                self.vocab[word]
                if self.vocab[word] != int(pieces[1]):
                    raise Exception("The read word in the vocab does not match the ID it was given in the vocab file. Please check the vocab file.")
                
        return

