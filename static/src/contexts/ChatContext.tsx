import React, { createContext, useContext, useState, useEffect } from 'react';
import { useSocket } from './SocketContext';
import { useAuth } from './AuthContext';
import axios from 'axios';

interface Message {
  id: number;
  content: string;
  role: 'user' | 'assistant';
  created_at: string;
}

interface Conversation {
  id: number;
  title: string;
  starred: boolean;
  created_at: string;
  messages: Message[];
}

interface ChatContextType {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  loading: boolean;
  sendMessage: (content: string, files?: File[]) => Promise<void>;
  createNewConversation: () => Promise<void>;
  loadConversation: (id: number) => Promise<void>;
  starConversation: (id: number) => Promise<void>;
}

const ChatContext = createContext<ChatContextType>({
  conversations: [],
  currentConversation: null,
  loading: false,
  sendMessage: async () => {},
  createNewConversation: async () => {},
  loadConversation: async () => {},
  starConversation: async () => {},
});

export const useChat = () => useContext(ChatContext);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(false);
  const { socket } = useSocket();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (socket) {
      socket.on('message', handleNewMessage);
      socket.on('conversation_update', handleConversationUpdate);
      return () => {
        socket.off('message', handleNewMessage);
        socket.off('conversation_update', handleConversationUpdate);
      };
    }
  }, [socket, currentConversation]);

  const handleConversationUpdate = (data: { id: number; title: string }) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === data.id ? { ...conv, title: data.title } : conv
      )
    );
    if (currentConversation?.id === data.id) {
      setCurrentConversation(prev => prev ? { ...prev, title: data.title } : null);
    }
  };

  const loadConversations = async () => {
    try {
      const response = await axios.get('/api/conversations');
      setConversations(response.data);
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const handleNewMessage = (message: Message) => {
    if (currentConversation) {
      setCurrentConversation(prev => {
        if (!prev) return null;
        return {
          ...prev,
          messages: [...prev.messages, message]
        };
      });
    }
  };

  const sendMessage = async (content: string, files?: File[]) => {
    if (!socket || !currentConversation) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('message', content);
      formData.append('conversation_id', currentConversation.id.toString());
      
      if (files) {
        files.forEach(file => {
          formData.append('files[]', file);
        });
      }

      socket.emit('message', formData);
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setLoading(false);
    }
  };

  const createNewConversation = async () => {
    try {
      const response = await axios.post('/api/conversations');
      const newConversation = response.data;
      setConversations(prev => [newConversation, ...prev]);
      await loadConversation(newConversation.id);
    } catch (error) {
      console.error('Error creating new conversation:', error);
    }
  };

  const loadConversation = async (id: number) => {
    try {
      const response = await axios.get(`/api/conversations/${id}`);
      setCurrentConversation(response.data);
    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  const starConversation = async (id: number) => {
    try {
      await axios.post(`/api/conversations/${id}/star`);
      setConversations(prev =>
        prev.map(conv =>
          conv.id === id ? { ...conv, starred: !conv.starred } : conv
        )
      );
    } catch (error) {
      console.error('Error starring conversation:', error);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        conversations,
        currentConversation,
        loading,
        sendMessage,
        createNewConversation,
        loadConversation,
        starConversation,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};