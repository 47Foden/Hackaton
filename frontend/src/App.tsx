import { useState } from 'react';
import { StartScreen } from './screens/StartScreen';
import { VoiceOrderScreen } from './screens/VoiceOrderScreen';
import { OrderScreen } from './screens/OrderScreen';

export function App() {
  const [screen, setScreen] = useState<'start' | 'order' | 'voice'>('start');
  // The order screen is mounted only for the lifetime of one order session.
  return screen === 'start'
    ? <StartScreen onStart={() => setScreen('order')} onVoice={() => setScreen('voice')} />
    : screen === 'voice' ? <VoiceOrderScreen onHome={() => setScreen('start')} /> : <OrderScreen onHome={() => setScreen('start')} />;
}
