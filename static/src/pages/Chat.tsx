import React, { useState, useRef, useEffect } from 'react';
import { Box, Paper, TextField, IconButton, Typography, CircularProgress, List, ListItem, ListItemText, Drawer, useTheme, useMediaQuery, Button, Avatar, Menu as MuiMenu, MenuItem, Divider } from '@mui/material';
import { Send, AttachFile, Menu, Star, StarBorder, AccountCircle, ExitToApp } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useChat } from '../contexts/ChatContext';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Chat: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();

  const {
    conversations,
    currentConversation,
    loading,
    sendMessage,
    createNewConversation,
    loadConversation,
    starConversation
  } = useChat();

  const { user, logout } = useAuth();

  useEffect(() => {
    scrollToBottom();
  }, [currentConversation?.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (message.trim() || files.length > 0) {
      await sendMessage(message, files);
      setMessage('');
      setFiles([]);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFiles(Array.from(event.target.files));
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchor(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchor(null);
  };

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        sx={{
          width: 240,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        <Box sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <Button
            fullWidth
            variant="contained"
            onClick={createNewConversation}
            sx={{ mb: 2 }}
          >
            New Chat
          </Button>
          <Typography variant="h6" sx={{ mb: 1 }}>Conversations</Typography>
          <List sx={{ 
            flexGrow: 1, 
            overflowY: 'auto',
            maxHeight: 'calc(100vh - 200px)', // Adjusted height to make room for user panel
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: 'transparent',
            },
            '&::-webkit-scrollbar-thumb': {
              background: 'rgba(0, 0, 0, 0.2)',
              borderRadius: '3px',
            }
          }}>
            {conversations.map((conv) => (
              <motion.div
                key={conv.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
              >
                <ListItem
                  button
                  selected={currentConversation?.id === conv.id}
                  onClick={() => loadConversation(conv.id)}
                >
                  <ListItemText primary={conv.title} />
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      starConversation(conv.id);
                    }}
                  >
                    {conv.starred ? <Star color="primary" /> : <StarBorder />}
                  </IconButton>
                </ListItem>
              </motion.div>
            ))}
          </List>
        </Box>
        
        {/* User Panel */}
        <Box 
          sx={{ 
            p: 2, 
            borderTop: 1, 
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            '&:hover': {
              bgcolor: 'rgba(0, 0, 0, 0.04)'
            },
            transition: 'background-color 0.2s'
          }}
          onClick={handleUserMenuOpen}
        >
          <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
            {user?.username?.charAt(0).toUpperCase() || <AccountCircle />}
          </Avatar>
          <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
            <Typography noWrap variant="subtitle2">
              {user?.username || 'User'}
            </Typography>
            <Typography noWrap variant="caption" color="text.secondary">
              {user?.email || ''}
            </Typography>
          </Box>
        </Box>
        
        {/* User Menu */}
        <MuiMenu
          anchorEl={userMenuAnchor}
          open={Boolean(userMenuAnchor)}
          onClose={handleUserMenuClose}
          transformOrigin={{ horizontal: 'left', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}
          PaperProps={{
            elevation: 3,
            sx: { width: 220, mt: 1 }
          }}
        >
          <MenuItem onClick={handleUserMenuClose}>
            <AccountCircle sx={{ mr: 2 }} />
            Profile
          </MenuItem>
          <Divider />
          <MenuItem 
            onClick={() => {
              handleUserMenuClose();
              handleLogout();
            }}
            sx={{ color: 'error.main' }}
          >
            <ExitToApp sx={{ mr: 2 }} />
            Logout
          </MenuItem>
        </MuiMenu>
      </Drawer>

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <IconButton onClick={() => setDrawerOpen(!drawerOpen)} sx={{ mr: 2 }}>
            <Menu />
          </IconButton>
          <Typography variant="h6">
            {currentConversation?.title || 'New Chat'}
          </Typography>
        </Box>

        <Paper
          sx={{
            flexGrow: 1,
            mb: 2,
            p: 2,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <AnimatePresence>
            {currentConversation?.messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    mb: 2,
                  }}
                >
                  <Paper
                    sx={{
                      p: 2,
                      maxWidth: '70%',
                      bgcolor: msg.role === 'user' ? 'primary.main' : 'background.paper',
                    }}
                  >
                    <Typography>{msg.content}</Typography>
                  </Paper>
                </Box>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </Paper>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <input
            type="file"
            multiple
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          <IconButton
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
          >
            <AttachFile />
          </IconButton>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            disabled={loading}
            sx={{ flexGrow: 1 }}
          />
          <IconButton
            onClick={handleSend}
            disabled={loading || (!message.trim() && !files.length)}
            color="primary"
          >
            {loading ? <CircularProgress size={24} /> : <Send />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
};

export default Chat;