import React from 'react';
import ReactDOM from 'react-dom/client';
import CourseHub from './components/CourseHub';
import ExpertStudio from './components/ExpertStudio';
import './styles.css';
const isStudio = window.location.pathname === '/studio' || window.location.pathname.startsWith('/studio/');
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{isStudio ? <ExpertStudio /> : <CourseHub />}</React.StrictMode>);
