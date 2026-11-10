import type { ServiceType } from './api/contracts';
import { useState } from 'react';
import { StartScreen } from './screens/StartScreen';
import { VoiceOrderScreen } from './screens/VoiceOrderScreen';
import { OrderScreen } from './screens/OrderScreen';

export function App() {
  const [screen, setScreen] = useState<'start' | 'order' | 'voice'>('start');
  const [serviceType, setServiceType] = useState<ServiceType>('DINE_IN');
  // The order screen is mounted only for the lifetime of one order session.
  return screen === 'start'
    ? <StartScreen serviceType={serviceType} onServiceType={setServiceType} onStart={() => setScreen('order')} onVoice={() => setScreen('voice')} />
    : screen === 'voice' ? <VoiceOrderScreen serviceType={serviceType} onHome={() => setScreen('start')} /> : <OrderScreen serviceType={serviceType} onHome={() => setScreen('start')} />;
}
