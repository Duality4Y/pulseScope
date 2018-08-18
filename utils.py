import numpy

def chunks(inputList, size):
    """ Yields successive size chunks from inputList. """
    for i in range(0, len(inputList), size):
        yield inputList[i:i + size]

def mean(a):
    """ returns the average of a list. """
    return float(sum(a)) / float(len(a))

def average_lists(lists):
    """ returns a a few lists averaged together. """
    return map(mean, zip(*lists))

# if data is interlaced audio then return a tuple with left and right data
def channels(data):
    """
    seperate interlaced data,
    and return the left and right channel.
    """
    return (data[0::2], data[1::2])

def toLinear(data, logScale=20):
    value = logScale * numpy.log10(value)

def chunkMean(chunk):
    """ Simply return mean of chunk. """
    return mean(chunk)

def chunkFirstPoint(chunk):
    """ Simply return the first point in the chunk. """
    return chunk[0]


# object for doing averages on lists of numbers.
class Average(object):
    def __init__(self, size=20):
        self.size = size
        self.lists = []

    def averageLists(self, lists):
        return list(map(mean, zip(*lists)))

    def getSize(self):
        return self.size

    def setSize(self, value):
        self.size = value

    def average(self, values=None):
        """
        add the new list and return the average of those lists.
        else if values == None then simply return what we have.
        this way we can also store data and retrieve what we hadd without
        modifing it!
        """
        if values is not None:
            self.lists.append(values)
        if len(self.lists) > self.size:
            del self.lists[0]
        return self.averageLists(self.lists)

class Buffer(object):
    def __init__(self, length=10, chunksize=1024):
        self.data = []
        self.length = length
        self.chunksize = chunksize
        self.dataslice = slice(self.chunksize, -1, 1)

    def add(self, inputData):
        """
            This function adds data to a buffered list of data.
            Assumes that the inputData is a list of fixed length.
        """
        # remove the first one if the length is indicates it's full
        if len(self.data) == self.chunksize * self.length:
            self.data = self.data[self.chunksize::1]

        self.data.extend(inputData)

    @property
    def size(self):
        return len(self.data)

    @property
    def buffer(self):
        return self.data

    @property
    def filled(self):
        return self.size == (self.length * self.chunksize)

class FramedBuffer(Buffer):
    def __init__(self, *args, **kwargs):
        super(FramedBuffer, self).__init__(*args, **kwargs)

    @property
    def buffer(self):
        if self.length == 1:
            return self.data
        else:
            return self.data[math.floor(self.chunksize / 2):self.size - math.floor(self.chunksize / 2):1]
