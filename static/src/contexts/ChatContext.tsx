import React, { createContext, useContext, useState, useEffect } from 'react';
import { useSocket } from './SocketContext';
import { useAuth } from './AuthContext';
import axios from 'axios';
import { AlertColor } from '@mui/material/Alert';

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

interface VideoParams {
  durationSeconds: number;
  numberOfVideos: number;
  video_aspect_ratio: string;
}

interface ChatContextType {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  loading: boolean;
  sendMessage: (content: string, files?: File[], model?: string, videoParams?: VideoParams) => Promise<void>;
  createNewConversation: () => Promise<void>;
  loadConversation: (id: number) => Promise<void>;
  starConversation: (id: number) => Promise<void>;
  // Snackbar state and functions
  snackbarOpen: boolean;
  snackbarMessage: string;
  snackbarSeverity: AlertColor;
  showSnackbar: (message: string, severity?: AlertColor) => void;
  closeSnackbar: () => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const useChat = () => useContext(ChatContext);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(false);
  const { socket } = useSocket();
  const { isAuthenticated } = useAuth();

  // Snackbar state
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<AlertColor>('info');

  const showSnackbar = (message: string, severity: AlertColor = 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };

  const closeSnackbar = () => {
    setSnackbarOpen(false);
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (socket) {
      socket.on('message', handleNewMessage);
      socket.on('message_progress', handleMessageProgress);
      socket.on('conversation_update', handleConversationUpdate);
      return () => {
        socket.off('message', handleNewMessage);
        socket.off('message_progress', handleMessageProgress);
        socket.off('conversation_update', handleConversationUpdate);
      };
    }
  }, [socket, currentConversation]); // Added currentConversation to dependencies

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
      showSnackbar('Failed to load conversations.', 'error');
    }
  };

  const handleNewMessage = (newMessage: Message) => {
    setCurrentConversation(prev => {
      if (!prev) return null;

      // If the message is from the assistant and is 'done', replace the last assistant message if it's partial
      // Or, if it's a user message, or a new assistant message.
      const existingMessageIndex = prev.messages.findIndex(m => m.id === newMessage.id && m.role === newMessage.role);

      if (existingMessageIndex !== -1) {
        // Update existing message (e.g., final content for a streamed message)
        const updatedMessages = [...prev.messages];
        updatedMessages[existingMessageIndex] = newMessage;
        return { ...prev, messages: updatedMessages };
      } else {
        // Add new message
        return { ...prev, messages: [...prev.messages, newMessage] };
      }
    });
    setLoading(false); // Stop loading when a full message is received
  };

  const handleMessageProgress = (data: { chunk: string; assistant_message_id: number }) => {
    setCurrentConversation(prev => {
      if (!prev) return null;
      const messages = [...prev.messages];
      const lastMessage = messages[messages.length - 1];

      if (lastMessage && lastMessage.role === 'assistant' && lastMessage.id === data.assistant_message_id) {
        // Append chunk to the last assistant message
        lastMessage.content += data.chunk;
        return { ...prev, messages };
      } else if (lastMessage?.role !== 'assistant' || lastMessage.id !== data.assistant_message_id) {
        // If the last message isn't the one we're getting progress for,
        // or if there's no assistant message yet, create one.
        // This assumes the backend sends an initial 'message' event with an ID
        // before sending 'message_progress'. If not, this needs adjustment.
        // For now, we'll assume an initial message with ID is sent.
        // A more robust way would be to ensure the backend sends a message object first,
        // even if empty, then progress events update it.
         messages.push({
          id: data.assistant_message_id, // Use the ID from the progress event
          content: data.chunk,
          role: 'assistant',
          created_at: new Date().toISOString(),
        });
        return { ...prev, messages };
      }
      return prev;
    });
    setLoading(true); // Keep loading while progressing
  };

  const sendMessage = async (content: string, files?: File[], model: string = 'gpt-4', videoParams?: VideoParams) => {
    if (!currentConversation) return;

    const userMessage: Message = {
      id: Date.now(), // Temporary ID for optimistic update, backend will assign final ID
      content,
      role: 'user',
      created_at: new Date().toISOString(),
    };

    // Optimistic update for user message
    setCurrentConversation(prev => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, userMessage],
      };
    });

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('message', content);
      formData.append('conversation_id', currentConversation.id.toString());
      formData.append('model', model); 
      
      if (files) {
        files.forEach(file => {
          formData.append('attachments', file); 
        });
      }

      if (model === 'kkty2-video' && videoParams) {
        formData.append('durationSeconds', videoParams.durationSeconds.toString());
        formData.append('numberOfVideos', videoParams.numberOfVideos.toString());
        formData.append('video_aspect_ratio', videoParams.video_aspect_ratio);
      }
      // Add other parameters as needed by backend, e.g.:
      // formData.append('web_search', 'true');

      await axios.post('/chat', formData);
      // Backend will send socket events for assistant's response ('message' and 'message_progress')
      // setLoading(false) will be handled by handleNewMessage or if an error occurs.

    } catch (error) {
      console.error('Error sending message:', error);
      showSnackbar('Failed to send message. Please try again.', 'error');
      setCurrentConversation(prev => {
        if (!prev) return null;
        return {
          ...prev,
          messages: prev.messages.filter(m => m.id !== userMessage.id) // Remove optimistic message on error
        };
      });
      setLoading(false);
    }
    // setLoading(false) is managed by handleNewMessage or error cases.
  };

  const createNewConversation = async () => {
    try {
      const response = await axios.post('/api/conversations');
      const newConversation = response.data;
      setConversations(prev => [newConversation, ...prev]);
      await loadConversation(newConversation.id);
      showSnackbar('New conversation created!', 'success');
    } catch (error) {
      console.error('Error creating new conversation:', error);
      showSnackbar('Failed to create new conversation.', 'error');
    }
  };

  const loadConversation = async (id: number) => {
    try {
      const response = await axios.get(`/api/conversations/${id}`);
      setCurrentConversation(response.data);
    } catch (error) {
      console.error('Error loading conversation:', error);
      showSnackbar('Failed to load conversation details.', 'error');
    }
  };

  const starConversation = async (id: number) => {
    try {
      const response = await axios.post(`/api/conversations/${id}/star`);
      // Assuming backend returns { starred: boolean }
      const updatedStarredStatus = response.data.starred; 
      setConversations(prev =>
        prev.map(conv =>
          conv.id === id ? { ...conv, starred: updatedStarredStatus } : conv
        )
      );
      showSnackbar(updatedStarredStatus ? 'Conversation starred!' : 'Conversation unstarred.', 'info');
    } catch (error) {
      console.error('Error starring conversation:', error);
      showSnackbar('Failed to update conversation star status.', 'error');
    }
  };

  const contextValue: ChatContextType = {
    conversations,
    currentConversation,
    loading,
    sendMessage,
    createNewConversation,
    loadConversation,
    starConversation,
    snackbarOpen,
    snackbarMessage,
    snackbarSeverity,
    showSnackbar,
    closeSnackbar,
  };

  return (
    <ChatContext.Provider value={contextValue}>
      {children}
    </ChatContext.Provider>
  );
};

// Custom hook to use chat context, ensuring it's used within ChatProvider
export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};